"""
Voice-agent integration client.

Triggers a LiveKit voice session on the capstone.voice-src server when a fall
is detected AND the car has come to a stop next to the fallen person. The
voice worker (already running on the laptop) is then dispatched to that room
and starts the NightOfficerAgent.

Phase 1 (this file):
    • Sync POST /api/v1/session/start to mint a token.
    • Optionally join the returned LiveKit room as a SILENT participant
      (no mic publish, no speaker subscribe yet) so the worker is actually
      dispatched. This still requires `pip install livekit`.
    • If the `livekit` package isn't installed, the trigger logs the session
      details and exits gracefully — the worker won't be dispatched without
      a participant, but the API plumbing is verified.

Phase 2 (later, when mic + speaker are plugged in):
    • Add `sounddevice`-based mic capture, feed into livekit AudioSource.
    • Subscribe to the incoming TTS track, route frames to the speaker.
    • See _async_join_room for the TODO locations.
"""

from __future__ import annotations

import asyncio
import threading
import time
from dataclasses import dataclass
from typing import Optional

import requests


try:
    from livekit import rtc as _lk_rtc  # type: ignore
    _HAS_LIVEKIT = True
except Exception:
    _lk_rtc = None  # type: ignore
    _HAS_LIVEKIT = False


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
        False for `end_after_no_fall_seconds`. `_last_fall_at` is refreshed
        every time we see falling=True (including while still approaching)
        so brief YOLO flickers don't tear down an active session.
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
                # Still moving toward the person — reset the "arrived" timer
                # so the trigger debounce only counts time spent stopped.
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

        # Respect retry cooldown after a previous failure.
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
                    "Phase 1 stops here. Install with: pip install livekit"
                )
            return True
        except Exception as exc:
            # Keep the message short; full repr was filling the log.
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
            def _on_connected() -> None:
                print(f"[voice] room CONNECTED ({session.room_name})")

            @self._room.on("track_subscribed")
            def _on_subscribed(track, publication, participant) -> None:
                print(
                    f"[voice] subscribed track kind={track.kind} "
                    f"from {participant.identity}"
                )
                # Phase 2 TODO: if track.kind == audio, route frames to speaker.

            @self._room.on("disconnected")
            def _on_disconnected(*_a) -> None:
                print("[voice] room disconnected")

            await self._room.connect(session.livekit_url, session.token)
            # Phase 2 TODO:
            #   source = _lk_rtc.AudioSource(sample_rate=48000, num_channels=1)
            #   track  = _lk_rtc.LocalAudioTrack.create_audio_track("mic", source)
            #   await self._room.local_participant.publish_track(track, ...)
            #   feed source.capture_frame(...) from a sounddevice InputStream.
        except Exception as exc:
            print(f"[voice] join-room FAILED: {exc}")
            self._room = None

    async def _async_leave_room(self) -> None:
        if self._room is None:
            return
        try:
            await self._room.disconnect()
        except Exception as exc:
            print(f"[voice] leave-room error: {exc}")
        finally:
            self._room = None
