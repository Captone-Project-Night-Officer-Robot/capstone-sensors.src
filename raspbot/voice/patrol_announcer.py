"""
Patrol announcer — plays the voice-src patrol announcement while driving.

The *speech* is owned by the voice server (capstone.voice-src): it renders a
short bilingual safety message (English + Korean) with the SAME ElevenLabs
voice as the Night Officer agent and serves it at

    GET {VOICE_API_URL}/api/v1/announce/patrol.wav

The Pi just fetches that WAV once at startup and loops it through the speaker
while the car is line-following / searching / dodging — exactly the way it
plays the agent's TTS during a fall conversation. It goes silent the instant
a fall starts being verified, so the voice agent can take over the speaker.

Design notes:
    • One HTTP fetch at start(); the clip is cached in memory and replayed.
    • Playback is interruptible: the thread checks an "active" flag between
      small audio blocks, so set_active(False) silences it within ~50 ms.
    • The OutputStream is opened per utterance and closed afterwards, so the
      speaker is free for the voice agent during a conversation.

If sounddevice/numpy is missing or the server is unreachable, start() raises
with a clear message and the caller disables the feature gracefully.
"""

from __future__ import annotations

import io
import threading
import time
import wave
from typing import Any

import requests

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


class PatrolAnnouncer:
    def __init__(
        self,
        api_url: str,
        gap_sec: float = 6.0,
        speaker_device: int | str | None = None,
        fetch_timeout_sec: float = 10.0,
        path: str = "/api/v1/announce/patrol.wav",
    ) -> None:
        self.api_url = api_url.rstrip("/")
        self.path = path
        self.gap_sec = max(0.0, gap_sec)
        self.speaker_device = speaker_device
        self.fetch_timeout_sec = fetch_timeout_sec

        self._clip: tuple[Any, int] | None = None   # (np.int16 samples, rate)
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._active_event = threading.Event()
        self._stream = None                          # sounddevice.OutputStream
        self._stream_lock = threading.Lock()

    # ─── lifecycle ────────────────────────────────────────────────

    def start(self) -> None:
        if self._thread is not None:
            return
        if not _HAS_SOUNDDEVICE or _sd is None:
            raise RuntimeError(
                "sounddevice not available — cannot play announcements. "
                "Install: sudo apt install libportaudio2 && pip install sounddevice"
            )
        if not _HAS_NUMPY or _np is None:
            raise RuntimeError("numpy not available — cannot play announcements.")

        data, src_rate = self._fetch_clip()

        # Many cheap USB audio devices (e.g. UACDemoV1) reject 24 kHz — the
        # rate ElevenLabs emits — and only accept 48 kHz. Pick a rate the
        # speaker actually supports and resample the clip to it once here, so
        # the playback OutputStream always opens cleanly.
        out_rate = self._pick_output_rate(src_rate)
        if out_rate != src_rate:
            data = self._resample(data, src_rate, out_rate)
            print(f"[announce] resampled {src_rate}Hz → {out_rate}Hz for speaker")
        self._clip = (data, out_rate)

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="patrol-announcer"
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._active_event.clear()
        with self._stream_lock:
            if self._stream is not None:
                try:
                    self._stream.abort()
                except Exception:
                    pass
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def set_active(self, active: bool) -> None:
        """Called every control-loop frame. True while the car is driving;
        False pauses announcements (fall verify / voice handoff)."""
        if active:
            self._active_event.set()
        else:
            self._active_event.clear()

    # ─── fetch ────────────────────────────────────────────────────

    def _fetch_clip(self) -> tuple[Any, int]:
        url = f"{self.api_url}{self.path}"
        resp = requests.get(url, timeout=self.fetch_timeout_sec)
        resp.raise_for_status()

        with wave.open(io.BytesIO(resp.content), "rb") as wf:
            rate = wf.getframerate()
            channels = wf.getnchannels()
            raw = wf.readframes(wf.getnframes())
        data = _np.frombuffer(raw, dtype=_np.int16)
        if channels > 1:
            data = data.reshape(-1, channels)[:, 0].copy()
        print(
            f"[announce] fetched patrol clip from {url} "
            f"({len(data) / rate:.1f}s @ {rate}Hz)"
        )
        return (data, rate)

    # ─── sample-rate handling ─────────────────────────────────────

    def _pick_output_rate(self, src_rate: int) -> int:
        """Return a samplerate the speaker accepts, preferring the source rate."""
        if _sd is None:
            return src_rate

        default_sr = 0
        try:
            info = _sd.query_devices(self.speaker_device, "output")
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
                    device=self.speaker_device,
                    samplerate=r,
                    channels=1,
                    dtype="int16",
                )
                return r
            except Exception:
                continue
        return src_rate  # nothing matched; let _play surface the error

    def _resample(self, data: Any, src: int, dst: int) -> Any:
        """Linear resample int16 mono. Good enough for a speech announcement."""
        if src == dst or len(data) == 0:
            return data
        n_dst = int(round(len(data) * dst / src))
        if n_dst <= 0:
            return data
        x_src = _np.linspace(0.0, 1.0, num=len(data), endpoint=False)
        x_dst = _np.linspace(0.0, 1.0, num=n_dst, endpoint=False)
        out = _np.interp(x_dst, x_src, data.astype(_np.float32))
        return out.astype(_np.int16)

    # ─── playback thread ──────────────────────────────────────────

    def _run(self) -> None:
        while not self._stop_event.is_set():
            # Block cheaply until the car is driving.
            if not self._active_event.wait(timeout=0.25):
                continue
            if self._clip is not None:
                data, rate = self._clip
                self._play(data, rate)
            self._sleep_interruptible(self.gap_sec)

    def _play(self, data: Any, rate: int) -> None:
        if _sd is None:
            return
        block = 1024  # ~43 ms at 24 kHz → interruption latency ceiling
        try:
            with self._stream_lock:
                stream = _sd.OutputStream(
                    samplerate=rate,
                    channels=1,
                    dtype="int16",
                    device=self.speaker_device,
                )
                stream.start()
                self._stream = stream
        except Exception as exc:
            print(f"[announce] speaker open FAILED: {exc}")
            with self._stream_lock:
                self._stream = None
            return

        try:
            i = 0
            n = len(data)
            while i < n:
                if self._stop_event.is_set() or not self._active_event.is_set():
                    break
                stream.write(data[i:i + block])
                i += block
        except Exception as exc:
            print(f"[announce] speaker write err: {exc}")
        finally:
            with self._stream_lock:
                try:
                    stream.stop()
                    stream.close()
                except Exception:
                    pass
                self._stream = None

    def _sleep_interruptible(self, sec: float) -> None:
        end = time.monotonic() + sec
        while time.monotonic() < end:
            if self._stop_event.is_set() or not self._active_event.is_set():
                return
            time.sleep(0.05)
