"""
Per-track-id debounce gate for YOLO fall detections.

The fall-detection server runs Ultralytics' object tracker (BoT-SORT /
ByteTrack), so each person has a stable `track_id` across frames. This
verifier holds each track's first-falling timestamp and promotes to
"confirmed" once that ID has been continuously falling for
`cfg.FALL_VERIFY_SECONDS`.

Status semantics (mirrors the simpler single-state earlier version, but
now per track-id):
    "idle"       — no falling track active
    "verifying"  — at least one track is falling, none confirmed yet
    "confirmed"  — at least one track has held falling continuously
                   for the verify window. That ID's confirmed status
                   persists until it stops falling.

The car stops in *both* verifying and confirmed; only confirmed should
emit a map pin and unblock the voice trigger.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Iterable, Literal

FallStatus = Literal["idle", "verifying", "confirmed"]


@dataclass
class VerifierTick:
    status: FallStatus = "idle"
    confirmed_ids: list[int] = field(default_factory=list)
    verifying_ids: list[int] = field(default_factory=list)
    # Of all currently-confirmed track IDs, the one that has been falling
    # the longest. Useful as the "primary subject" for pins / voice.
    primary_id: int | None = None
    # held_seconds[track_id] = how long that ID has been continuously falling.
    held_seconds: dict[int, float] = field(default_factory=dict)


class FallVerifier:
    def __init__(self, verify_seconds: float) -> None:
        self.verify_seconds = max(0.0, float(verify_seconds))
        # track_id -> time.time() when that ID started its current falling streak
        self._held_since: dict[int, float] = {}
        self._confirmed: set[int] = set()
        self._last_tick = VerifierTick()

    @property
    def status(self) -> FallStatus:
        return self._last_tick.status

    def confirmed_ids(self) -> list[int]:
        return list(self._last_tick.confirmed_ids)

    def primary_id(self) -> int | None:
        return self._last_tick.primary_id

    def held_seconds(self, track_id: int | None = None,
                     now: float | None = None) -> float:
        """Held time for one ID (defaults to primary), or 0 if not tracking."""
        if track_id is None:
            track_id = self.primary_id()
        if track_id is None or track_id not in self._held_since:
            return 0.0
        t = time.time() if now is None else now
        return max(0.0, t - self._held_since[track_id])

    def update(self, falling_ids: Iterable[int],
               now: float | None = None) -> VerifierTick:
        t = time.time() if now is None else now
        seen = {int(x) for x in falling_ids}

        # Drop tracks that are no longer falling — immediate reset for that ID.
        for tid in list(self._held_since.keys()):
            if tid not in seen:
                del self._held_since[tid]
                self._confirmed.discard(tid)

        # Update active tracks; promote to confirmed when held long enough.
        for tid in seen:
            self._held_since.setdefault(tid, t)
            if t - self._held_since[tid] >= self.verify_seconds:
                self._confirmed.add(tid)

        held = {tid: t - since for tid, since in self._held_since.items()}

        if self._confirmed:
            status: FallStatus = "confirmed"
            primary = max(self._confirmed, key=lambda i: held.get(i, 0.0))
        elif self._held_since:
            status = "verifying"
            primary = max(self._held_since, key=lambda i: held.get(i, 0.0))
        else:
            status = "idle"
            primary = None

        self._last_tick = VerifierTick(
            status=status,
            confirmed_ids=sorted(self._confirmed),
            verifying_ids=sorted(set(self._held_since) - self._confirmed),
            primary_id=primary,
            held_seconds=held,
        )
        return self._last_tick
