from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

Direction = Literal["straight", "left", "right", "no_line"]


@dataclass(frozen=True)
class LaneDetectionResult:
    direction: Direction
    confidence: float
    lane_center_x: Optional[int]
    frame_center_x: int
    line_count: int
    reason: str
