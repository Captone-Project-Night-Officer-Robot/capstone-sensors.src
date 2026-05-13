"""
White line detector using OpenCV HSV thresholding.

White-line condition:
- saturation is low
- brightness/value is high
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


class WhiteLineDetector:
    def detect(self, frame: np.ndarray) -> LineDetection:
        height, width = frame.shape[:2]

        roi_top = int(height * cfg.ROI_TOP_RATIO)
        roi = frame[roi_top:height, :]

        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

        lower_white = np.array([0, 0, cfg.WHITE_VALUE_MIN], dtype=np.uint8)
        upper_white = np.array([179, cfg.WHITE_SATURATION_MAX, 255], dtype=np.uint8)

        mask = cv2.inRange(hsv, lower_white, upper_white)

        if cfg.USE_MORPHOLOGY:
            kernel = np.ones((5, 5), np.uint8)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            return LineDetection(False, None, None, None, 0.0, mask)

        largest = max(contours, key=cv2.contourArea)
        area = float(cv2.contourArea(largest))

        if area < cfg.MIN_CONTOUR_AREA:
            return LineDetection(False, None, None, None, area, mask)

        moments = cv2.moments(largest)

        if moments["m00"] == 0:
            return LineDetection(False, None, None, None, area, mask)

        center_x = int(moments["m10"] / moments["m00"])
        center_y_in_roi = int(moments["m01"] / moments["m00"])
        center_y = roi_top + center_y_in_roi

        frame_center_x = width // 2
        offset_x = center_x - frame_center_x

        return LineDetection(True, center_x, center_y, offset_x, area, mask)


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

        text = f"WHITE LINE offset={detection.offset_x}px area={int(detection.area)}"
        cv2.putText(output, text, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 2)
    else:
        text = f"WHITE LINE NOT FOUND area={int(detection.area)}"
        cv2.putText(output, text, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 255), 2)

    return output
