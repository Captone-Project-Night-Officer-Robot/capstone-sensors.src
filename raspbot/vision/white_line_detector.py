"""
White line detector using OpenCV HSV thresholding + shape filtering.

White-line condition:
- saturation is low (pure white, not tinted)
- brightness/value is high
- AND the contour is line-shaped (long & thin), so ambient glare /
  ceiling-light reflections get rejected even when they pass HSV
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

import raspbot.config as cfg


@dataclass
class LineDetection:
    found: bool
    center_x: int | None
    center_y: int | None
    offset_x: int | None
    area: float
    mask: np.ndarray
    rejected: int = 0  # how many contours failed the shape/area filters


def _is_line_shaped(
    contour: np.ndarray, roi_area: float
) -> tuple[bool, float, float]:
    """Return (passes, area, aspect_ratio). Used to reject non-line blobs."""
    area = float(cv2.contourArea(contour))

    if area < cfg.MIN_CONTOUR_AREA:
        return False, area, 0.0

    if cfg.LINE_MAX_AREA_RATIO > 0 and roi_area > 0:
        if area > roi_area * cfg.LINE_MAX_AREA_RATIO:
            return False, area, 0.0

    if cfg.LINE_ASPECT_RATIO_MIN > 0:
        (_cx, _cy), (rw, rh), _angle = cv2.minAreaRect(contour)
        if rw < 1.0 or rh < 1.0:
            return False, area, 0.0
        aspect = max(rw, rh) / min(rw, rh)
        if aspect < cfg.LINE_ASPECT_RATIO_MIN:
            return False, area, aspect
        return True, area, aspect

    return True, area, 0.0


class WhiteLineDetector:
    def detect(self, frame: np.ndarray) -> LineDetection:
        height, width = frame.shape[:2]

        roi_top = int(height * cfg.ROI_TOP_RATIO)
        roi = frame[roi_top:height, :]
        roi_area = float(roi.shape[0] * roi.shape[1])

        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

        lower_white = np.array([0, 0, cfg.WHITE_VALUE_MIN], dtype=np.uint8)
        upper_white = np.array([179, cfg.WHITE_SATURATION_MAX, 255], dtype=np.uint8)

        mask = cv2.inRange(hsv, lower_white, upper_white)

        if cfg.USE_MORPHOLOGY:
            kernel = np.ones((5, 5), np.uint8)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(
            mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        if not contours:
            return LineDetection(False, None, None, None, 0.0, mask, 0)

        # Filter to line-shaped contours, then pick the largest of those.
        # Picking "largest overall" before filtering would let a big glare
        # blob steal the lock from a smaller but legitimate line section.
        candidates: list[tuple[np.ndarray, float]] = []
        rejected = 0
        for c in contours:
            passes, area, _aspect = _is_line_shaped(c, roi_area)
            if passes:
                candidates.append((c, area))
            else:
                rejected += 1

        if not candidates:
            # Report the biggest area we saw so debug logs are informative.
            biggest = max((cv2.contourArea(c) for c in contours), default=0.0)
            return LineDetection(False, None, None, None, float(biggest), mask, rejected)

        best, area = max(candidates, key=lambda ca: ca[1])

        moments = cv2.moments(best)
        if moments["m00"] == 0:
            return LineDetection(False, None, None, None, area, mask, rejected)

        center_x = int(moments["m10"] / moments["m00"])
        center_y_in_roi = int(moments["m01"] / moments["m00"])
        center_y = roi_top + center_y_in_roi

        frame_center_x = width // 2
        offset_x = center_x - frame_center_x

        return LineDetection(True, center_x, center_y, offset_x, area, mask, rejected)


def draw_debug(frame: np.ndarray, detection: LineDetection) -> np.ndarray:
    output = frame.copy()

    height, width = output.shape[:2]
    frame_center_x = width // 2

    cv2.line(output, (frame_center_x, 0), (frame_center_x, height), (255, 255, 255), 1)

    roi_top = int(height * cfg.ROI_TOP_RATIO)
    cv2.line(output, (0, roi_top), (width, roi_top), (255, 255, 0), 1)

    if detection.found and detection.center_x is not None and detection.center_y is not None:
        cv2.circle(output, (detection.center_x, detection.center_y), 8, (0, 0, 255), -1)

        cv2.line(
            output,
            (frame_center_x, detection.center_y),
            (detection.center_x, detection.center_y),
            (0, 255, 0),
            2,
        )

        text = (
            f"WHITE LINE offset={detection.offset_x}px "
            f"area={int(detection.area)} rejected={detection.rejected}"
        )
        cv2.putText(output, text, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 2)
    else:
        text = (
            f"WHITE LINE NOT FOUND  biggest_area={int(detection.area)}  "
            f"rejected={detection.rejected}"
        )
        cv2.putText(output, text, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 255), 2)

    return output
