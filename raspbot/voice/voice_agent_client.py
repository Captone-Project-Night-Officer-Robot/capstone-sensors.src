"""
Voice-agent integration client.

Triggers a LiveKit voice session on the capstone.voice-src server when a
fall is detected AND the car has stopped next to the fallen person. The
voice worker (already running on the laptop) is then dispatched into that
room and starts the NightOfficerAgent.

Phase 2 (this file):
    • Sync POST /api/v1/session/start to mint a token.
    • Join the returned LiveKit room from the Pi.
    • PUBLISH the Pi's mic as a LiveKit audio track (the agent's STT
      receives it and runs Silero VAD + ElevenLabs STT).
    • SUBSCRIBE to the agent's TTS track and play it through the Pi's
      speaker (sounddevice.OutputStream, sample rate auto-detected per
      incoming frame — exactly the pattern listen_local.py uses).

If `livekit` or `sounddevice` is missing on the Pi, the trigger still
fires and logs the session, but the corresponding side (room join or
audio I/O) is skipped gracefully so the line-follower keeps running.
"""

from __future__ import annotations

import asyncio
import queue
import threading
import time
from dataclasses import dataclass
from typing import Optional

import requests

import raspbot.config as cfg


try:
    from livekit import rtc as _lk_rtc  # type: ignore
    _HAS_LIVEKIT = True
except Exception:
    _lk_rtc = None  # type: ignore
    _HAS_LIVEKIT = False

try:
    import numpy as _np  # type: ignore
    _HAS_NUMPY = True
except Exception:
    _np = None  # type: ignore
    _HAS_NUMPY = False

try:
    import sounddevice as _sd  # type: ignore
    _HAS_SOUNDDEVICE = True
except Exception:
    _sd = None  # type: ignore
    _HAS_SOUNDDEVICE = False


def _pick_output_rate(device, src_rate: int, channels: int) -> int:
    """Return a samplerate the speaker accepts, preferring the source rate.

    Cheap USB audio devices (e.g. UACDemoV1) reject ElevenLabs' 24 kHz TTS
    and only accept 48 kHz — opening the stream at 24 kHz then fails with
    paInvalidSampleRate. Probe for a rate the device actually supports.
    """
    if _sd is None:
        return src_rate
    default_sr = 0
    try:
        info = _sd.query_devices(device, "output")
        default_sr = int(info.get("default_samplerate", 0))
    except Exception:
        pass
    candidates: list[int] = []
    for r in (src_rate, default_sr, 48000, 44100, 32000, 22050, 16000):
        if r and r not in candidates:
            candidates.append(r)
    for r in candidates:
        try:
            _sd.check_output_settings(
                device=device, samplerate=r, channels=channels, dtype="int16"
            )
            return r
        except Exception:
            continue
    return src_rate


def _resample_int16(data, src: int, dst: int):
    """Linear resample mono int16. Good enough for speech."""
    if _np is None or src == dst or len(data) == 0:
        return data
    n_dst = int(round(len(data) * dst / src))
    if n_dst <= 0:
        return data
    x_src = _np.linspace(0.0, 1.0, num=len(data), endpoint=False)
    x_dst = _np.linspace(0.0, 1.0, num=n_dst, endpoint=False)
    out = _np.interp(x_dst, x_src, data.astype(_np.float32))
    return out.astype(_np.int16)


@dataclass
class VoiceSession:
    room_name: str
    token: str
    livekit_url: str
    started_at: float


class VoiceAgentClient:
    """Owns voice-session state. Drive it by calling `tick()` every loop."""

    def __init__(
        self,
        api_url: str,
        robot_id: str,
        timeout_sec: float = 5.0,
        trigger_stop_seconds: float = 1.0,
        end_after_no_fall_seconds: float = 3.0,
        retry_cooldown_seconds: float = 5.0,
    ) -> None:
        self.api_url = api_url.rstrip("/")
        self.robot_id = robot_id
        self.timeout_sec = timeout_sec
        self.trigger_stop_seconds = trigger_stop_seconds
        self.end_after_no_fall_seconds = end_after_no_fall_seconds
        self.retry_cooldown_seconds = retry_cooldown_seconds

        self._session: Optional[VoiceSession] = None
        self._lock = threading.Lock()
        self._http = requests.Session()

        self._first_arrived_at: Optional[float] = None
        self._last_fall_at: Optional[float] = None
        self._last_failed_attempt_at: Optional[float] = None

        # LiveKit (only used if SDK installed)
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_thread: Optional[threading.Thread] = None
        self._room = None  # livekit.rtc.Room when active

        # Audio I/O (Phase 2)
        self._audio_source = None              # rtc.AudioSource (mic)
        self._mic_stream = None                # sounddevice.InputStream
        self._mic_queue: "queue.Queue[bytes]" = queue.Queue(
            maxsize=cfg.VOICE_MIC_QUEUE_MAX
        )
        self._mic_pump_task: Optional[asyncio.Task] = None
        self._spk_stream = None                # sounddevice.OutputStream (lazy)
        self._spk_stream_lock = threading.Lock()
        self._spk_out_rate: Optional[int] = None  # device rate (may differ from TTS)
        self._spk_tasks: list[asyncio.Task] = []
        self._audio_warned_no_sd = False

    # ─── public API ───────────────────────────────────────────────

    def is_active(self) -> bool:
        with self._lock:
            return self._session is not None

    def current_room(self) -> Optional[str]:
        with self._lock:
            return self._session.room_name if self._session else None

    def tick(self, *, falling: bool, arrived: bool) -> None:
        """Call once per control-loop iteration.

        Starts a session when `falling AND arrived` is held continuously
        for `trigger_stop_seconds`. Ends a session when `falling` has been
        False for `end_after_no_fall_seconds`. `_last_fall_at` refreshes
        every time we see falling=True so brief YOLO flickers don't tear
        down an active session.
        """
        now = time.time()

        if falling:
            self._last_fall_at = now
            if arrived:
                if self._first_arrived_at is None:
                    self._first_arrived_at = now
                if (
                    not self.is_active()
                    and now - self._first_arrived_at >= self.trigger_stop_seconds
                ):
                    self._start_session()
            else:
                self._first_arrived_at = None
        else:
            self._first_arrived_at = None
            if (
                self.is_active()
                and self._last_fall_at is not None
                and now - self._last_fall_at >= self.end_after_no_fall_seconds
            ):
                self._end_session()

    def shutdown(self) -> None:
        self._end_session()
        if self._loop is not None:
            try:
                self._loop.call_soon_threadsafe(self._loop.stop)
            except Exception:
                pass

    # ─── session start/stop ───────────────────────────────────────

    def _start_session(self) -> bool:
        now = time.time()

        if (
            self._last_failed_attempt_at is not None
            and now - self._last_failed_attempt_at < self.retry_cooldown_seconds
        ):
            return False

        try:
            resp = self._http.post(
                f"{self.api_url}/api/v1/session/start",
                json={"robot_id": self.robot_id},
                timeout=self.timeout_sec,
            )
            resp.raise_for_status()
            data = resp.json()
            session = VoiceSession(
                room_name=data["room_name"],
                token=data["token"],
                livekit_url=data["livekit_url"],
                started_at=time.time(),
            )
            with self._lock:
                self._session = session
            self._last_failed_attempt_at = None

            print(
                f"[voice] session started  room={session.room_name}  "
                f"url={session.livekit_url}"
            )

            if _HAS_LIVEKIT:
                self._ensure_loop()
                asyncio.run_coroutine_threadsafe(
                    self._async_join_room(session), self._loop  # type: ignore[arg-type]
                )
            else:
                print(
                    "[voice] livekit SDK not installed on the Pi — "
                    "session logged but no audio. Install: pip install livekit"
                )
            return True
        except Exception as exc:
            short = type(exc).__name__
            print(
                f"[voice] session start FAILED ({short}). "
                f"Retrying in {self.retry_cooldown_seconds:.0f}s. "
                f"Hint: is the voice API running at {self.api_url}?"
            )
            with self._lock:
                self._session = None
            self._last_failed_attempt_at = now
            return False

    def _end_session(self) -> None:
        with self._lock:
            if self._session is None:
                return
            room_name = self._session.room_name
            self._session = None

        print(f"[voice] session ended  room={room_name}")

        if _HAS_LIVEKIT and self._loop is not None and self._room is not None:
            asyncio.run_coroutine_threadsafe(
                self._async_leave_room(), self._loop
            )

    # ─── asyncio bridge ───────────────────────────────────────────

    def _ensure_loop(self) -> None:
        if self._loop_thread is not None:
            return
        ready = threading.Event()

        def _run() -> None:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            ready.set()
            self._loop.run_forever()

        self._loop_thread = threading.Thread(
            target=_run, daemon=True, name="voice-asyncio"
        )
        self._loop_thread.start()
        ready.wait()

    async def _async_join_room(self, session: VoiceSession) -> None:
        if not _HAS_LIVEKIT or _lk_rtc is None:
            return
        try:
            self._room = _lk_rtc.Room()

            @self._room.on("connected")
            def _on_connected() -> None:  # noqa: ARG001  — registered via decorator
                print(f"[voice] room CONNECTED ({session.room_name})")

            @self._room.on("track_subscribed")
            def _on_subscribed(track, publication, participant) -> None:  # noqa: ARG001
                if track.kind == _lk_rtc.TrackKind.KIND_AUDIO:
                    print(
                        f"[voice] subscribed audio track from "
                        f"{participant.identity}"
                    )
                    task = asyncio.create_task(self._consume_audio(track))
                    self._spk_tasks.append(task)

            @self._room.on("disconnected")
            def _on_disconnected(*_a) -> None:  # noqa: ARG001
                print("[voice] room disconnected")

            await self._room.connect(session.livekit_url, session.token)

            if cfg.VOICE_MIC_ENABLED:
                await self._publish_mic()

        except Exception as exc:
            print(f"[voice] join-room FAILED: {exc}")
            self._room = None

    async def _async_leave_room(self) -> None:
        # Stop mic capture before disconnecting so we don't keep capturing
        # into a dead AudioSource.
        await self._stop_mic()

        # Cancel any in-flight playback consumers.
        for task in self._spk_tasks:
            if not task.done():
                task.cancel()
        self._spk_tasks.clear()
        self._stop_speaker()

        if self._room is None:
            return
        try:
            await self._room.disconnect()
        except Exception as exc:
            print(f"[voice] leave-room error: {exc}")
        finally:
            self._room = None

    # ─── mic (publish) ────────────────────────────────────────────

    async def _publish_mic(self) -> None:
        if not _HAS_SOUNDDEVICE or _sd is None:
            if not self._audio_warned_no_sd:
                print(
                    "[voice] sounddevice not available — mic publish disabled. "
                    "Install: pip install sounddevice (+ portaudio system pkg)"
                )
                self._audio_warned_no_sd = True
            return
        if _lk_rtc is None:
            return

        sample_rate = cfg.VOICE_MIC_SAMPLE_RATE
        try:
            self._audio_source = _lk_rtc.AudioSource(
                sample_rate=sample_rate, num_channels=1
            )
            track = _lk_rtc.LocalAudioTrack.create_audio_track(
                "pi-mic", self._audio_source
            )
            options = _lk_rtc.TrackPublishOptions(
                source=_lk_rtc.TrackSource.SOURCE_MICROPHONE
            )
            await self._room.local_participant.publish_track(track, options)
            print(f"[voice] mic published  rate={sample_rate}Hz  ch=1")
        except Exception as exc:
            print(f"[voice] mic publish FAILED: {exc}")
            self._audio_source = None
            return

        # Drain any stale chunks left from a previous session.
        while not self._mic_queue.empty():
            try:
                self._mic_queue.get_nowait()
            except queue.Empty:
                break

        loop = asyncio.get_running_loop()
        block_frames = max(1, int(sample_rate * cfg.VOICE_MIC_BLOCK_MS / 1000))

        def _mic_callback(indata, frames, time_info, status):  # noqa: ARG001  PortAudio thread
            if status:
                # Underrun/overflow flags. Log sparingly — they happen.
                pass
            try:
                # Force int16 mono → bytes
                pcm = indata[:, 0].tobytes() if indata.ndim > 1 else indata.tobytes()
                self._mic_queue.put_nowait(pcm)
            except queue.Full:
                # Backpressure: drop the chunk. Better than blocking PortAudio.
                pass
            except Exception:
                pass

        try:
            self._mic_stream = _sd.InputStream(
                samplerate=sample_rate,
                channels=1,
                dtype="int16",
                blocksize=block_frames,
                callback=_mic_callback,
                device=cfg.VOICE_MIC_DEVICE,
            )
            self._mic_stream.start()
            print(
                f"[voice] mic capture started "
                f"device={cfg.VOICE_MIC_DEVICE or 'default'} "
                f"block={cfg.VOICE_MIC_BLOCK_MS}ms"
            )
        except Exception as exc:
            print(f"[voice] mic InputStream FAILED: {exc}")
            self._mic_stream = None
            return

        self._mic_pump_task = asyncio.create_task(self._mic_pump(loop))

    async def _mic_pump(self, loop: asyncio.AbstractEventLoop) -> None:
        """Pull PCM chunks from the cross-thread queue and capture them
        into the LiveKit AudioSource at the rate sounddevice produces them.
        """
        sample_rate = cfg.VOICE_MIC_SAMPLE_RATE
        try:
            while True:
                # Don't block the event loop — poll the thread-safe queue.
                try:
                    pcm = await asyncio.wait_for(
                        loop.run_in_executor(None, self._mic_queue.get, True, 0.5),
                        timeout=1.0,
                    )
                except (asyncio.TimeoutError, queue.Empty):
                    continue

                if self._audio_source is None or _lk_rtc is None:
                    break

                try:
                    frame = _lk_rtc.AudioFrame(
                        data=pcm,
                        sample_rate=sample_rate,
                        num_channels=1,
                        samples_per_channel=len(pcm) // 2,  # int16 = 2 bytes
                    )
                    await self._audio_source.capture_frame(frame)
                except Exception as exc:
                    print(f"[voice] capture_frame err: {exc}")
        except asyncio.CancelledError:
            pass

    async def _stop_mic(self) -> None:
        if self._mic_pump_task is not None and not self._mic_pump_task.done():
            self._mic_pump_task.cancel()
            try:
                await self._mic_pump_task
            except (asyncio.CancelledError, Exception):
                pass
        self._mic_pump_task = None

        if self._mic_stream is not None:
            try:
                self._mic_stream.stop()
                self._mic_stream.close()
            except Exception:
                pass
            self._mic_stream = None

        self._audio_source = None

    # ─── speaker (subscribe) ──────────────────────────────────────

    async def _consume_audio(self, track) -> None:
        """Pull frames from an agent's audio track and play them.

        Mirrors capstone.voice-src/src/listen_local.py — the OutputStream
        is opened lazily on the first frame so its sample rate matches the
        TTS engine (ElevenLabs typically emits 24kHz).
        """
        if not _HAS_SOUNDDEVICE or _sd is None:
            if not self._audio_warned_no_sd:
                print(
                    "[voice] sounddevice not available — speaker output disabled. "
                    "Install: pip install sounddevice"
                )
                self._audio_warned_no_sd = True
            return
        if not _HAS_NUMPY or _np is None:
            print("[voice] numpy not available — speaker output disabled.")
            return
        if _lk_rtc is None:
            return

        try:
            stream = _lk_rtc.AudioStream(track)
            async for ev in stream:
                frame = ev.frame
                if frame is None:
                    continue

                samples = _np.frombuffer(frame.data, dtype=_np.int16)
                channels = max(1, frame.num_channels)

                # Optional software gain. Promote to int32 to avoid wrap-
                # around, scale, then clip back into int16 range.
                gain = cfg.VOICE_SPEAKER_GAIN
                if gain != 1.0:
                    scaled = samples.astype(_np.int32) * gain
                    samples = _np.clip(scaled, -32768, 32767).astype(_np.int16)

                with self._spk_stream_lock:
                    if self._spk_stream is None:
                        out_rate = _pick_output_rate(
                            cfg.VOICE_SPEAKER_DEVICE, frame.sample_rate, channels
                        )
                        try:
                            self._spk_stream = _sd.OutputStream(
                                samplerate=out_rate,
                                channels=channels,
                                dtype="int16",
                                device=cfg.VOICE_SPEAKER_DEVICE,
                            )
                            self._spk_stream.start()
                            self._spk_out_rate = out_rate
                            note = (
                                f" (resampled from {frame.sample_rate}Hz)"
                                if out_rate != frame.sample_rate else ""
                            )
                            print(
                                f"[voice] speaker started "
                                f"{out_rate}Hz x{channels}ch "
                                f"device={cfg.VOICE_SPEAKER_DEVICE or 'default'}{note}"
                            )
                        except Exception as exc:
                            print(f"[voice] speaker open FAILED: {exc}")
                            self._spk_stream = None
                            return

                # Resample mono TTS to the device rate if they differ.
                if (
                    self._spk_out_rate is not None
                    and self._spk_out_rate != frame.sample_rate
                    and channels == 1
                ):
                    samples = _resample_int16(
                        samples, frame.sample_rate, self._spk_out_rate
                    )

                if channels > 1:
                    samples = samples.reshape(-1, channels)

                try:
                    self._spk_stream.write(samples)
                except Exception as exc:
                    print(f"[voice] speaker write err: {exc}")
                    break
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            print(f"[voice] audio consume err: {exc}")

    def _stop_speaker(self) -> None:
        with self._spk_stream_lock:
            if self._spk_stream is not None:
                try:
                    self._spk_stream.stop()
                    self._spk_stream.close()
                except Exception:
                    pass
                self._spk_stream = None
            self._spk_out_rate = None
