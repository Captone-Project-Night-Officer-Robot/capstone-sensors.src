from __future__ import annotations

from typing import Tuple

import cv2
import numpy as np

from raspbot.config import LaneConfig
from raspbot.vision.types import LaneDetectionResult


class GreenLaneDetector:
    """White-line detector kept under the old class name for compatibility.

    Why keep the name `GreenLaneDetector`?
    - Your current app already imports `GreenLaneDetector`.
    - By replacing only this file, you do not need to update other files.
    - Internally, this now detects a SINGLE WHITE LINE.

    White HSV logic:
    - White has low saturation.
    - White has high brightness/value.
    """

    def __init__(self, config: LaneConfig | None = None):
        self.config = config or LaneConfig()

        # Defaults for white line detection.
        # These use getattr() so this file works even if config.py still has old green fields.
        self.lower_white_h = getattr(self.config, "lower_white_h", 0)
        self.lower_white_s = getattr(self.config, "lower_white_s", 0)
        self.lower_white_v = getattr(self.config, "lower_white_v", 170)

        self.upper_white_h = getattr(self.config, "upper_white_h", 180)
        self.upper_white_s = getattr(self.config, "upper_white_s", 80)
        self.upper_white_v = getattr(self.config, "upper_white_v", 255)

        self.morphology_kernel_size = getattr(self.config, "morphology_kernel_size", 5)

        self.roi_top_ratio = getattr(self.config, "roi_top_ratio", 0.35)
        self.roi_left_top_ratio = getattr(self.config, "roi_left_top_ratio", 0.20)
        self.roi_right_top_ratio = getattr(self.config, "roi_right_top_ratio", 0.80)

        self.hough_rho = getattr(self.config, "hough_rho", 2)
        self.hough_theta_divisor = getattr(self.config, "hough_theta_divisor", 180)
        self.hough_threshold = getattr(self.config, "hough_threshold", 60)
        self.hough_min_line_length = getattr(self.config, "hough_min_line_length", 50)
        self.hough_max_line_gap = getattr(self.config, "hough_max_line_gap", 40)

        self.lane_center_tolerance_px = getattr(self.config, "lane_center_tolerance_px", 25)
        self.min_lines_required = getattr(self.config, "min_lines_required", 1)

    def detect(self, frame_bgr) -> tuple[LaneDetectionResult, object]:
        mask = self.apply_white_mask(frame_bgr)
        roi_mask = self.apply_roi(mask)
        debug_frame, line_positions = self.detect_lines(roi_mask, frame_bgr)
        result = self.navigate_from_lines(line_positions, frame_bgr.shape[1])
        self.draw_debug(debug_frame, roi_mask, result)
        return result, debug_frame

    def apply_white_mask(self, image_bgr):
        hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)

        lower_white = np.array([
            self.lower_white_h,
            self.lower_white_s,
            self.lower_white_v,
        ])

        upper_white = np.array([
            self.upper_white_h,
            self.upper_white_s,
            self.upper_white_v,
        ])

        mask = cv2.inRange(hsv, lower_white, upper_white)

        kernel = np.ones(
            (self.morphology_kernel_size, self.morphology_kernel_size),
            np.uint8,
        )

        # Remove small noise, then reconnect broken white-line pieces.
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        return mask

    def apply_roi(self, mask):
        height, width = mask.shape
        top = int(height * self.roi_top_ratio)

        # Trapezoid ROI focused on the road/track area in front of the car.
        polygon = np.array([[
            (0, height),
            (width, height),
            (int(width * self.roi_right_top_ratio), top),
            (int(width * self.roi_left_top_ratio), top),
        ]])

        roi = np.zeros_like(mask)
        cv2.fillPoly(roi, polygon, 255)

        return cv2.bitwise_and(mask, roi)

    def detect_lines(self, mask, original_frame):
        theta = np.pi / self.hough_theta_divisor

        lines = cv2.HoughLinesP(
            mask,
            self.hough_rho,
            theta,
            self.hough_threshold,
            minLineLength=self.hough_min_line_length,
            maxLineGap=self.hough_max_line_gap,
        )

        debug_frame = original_frame.copy()
        line_positions: list[Tuple[int, int]] = []

        if lines is not None:
            for line in lines:
                x1, y1, x2, y2 = line[0]

                cv2.line(debug_frame, (x1, y1), (x2, y2), (60, 200, 200), 4)
                line_positions.append(((x1 + x2) // 2, (y1 + y2) // 2))

        return debug_frame, line_positions

    def navigate_from_lines(
        self,
        line_positions: list[Tuple[int, int]],
        frame_width: int,
    ) -> LaneDetectionResult:
        frame_center = frame_width // 2

        if len(line_positions) < self.min_lines_required:
            return LaneDetectionResult(
                direction="no_line",
                confidence=0.0,
                lane_center_x=None,
                frame_center_x=frame_center,
                line_count=len(line_positions),
                reason="white_line_not_detected",
            )

        # For a single white line, use the average x-position of detected line midpoints.
        line_center = int(sum(p[0] for p in line_positions) / len(line_positions))

        offset = line_center - frame_center
        abs_offset = abs(offset)

        if abs_offset <= self.lane_center_tolerance_px:
            direction = "straight"
            reason = "white_line_centered"
        elif offset < 0:
            # White line is left of camera center, so steer left to re-center.
            direction = "left"
            reason = "white_line_left_of_frame_center"
        else:
            # White line is right of camera center, so steer right to re-center.
            direction = "right"
            reason = "white_line_right_of_frame_center"

        line_score = min(1.0, len(line_positions) / 5.0)
        offset_score = max(0.0, 1.0 - (abs_offset / max(frame_width / 2, 1)))
        confidence = round((line_score * 0.55) + (offset_score * 0.45), 3)

        return LaneDetectionResult(
            direction=direction,
            confidence=confidence,
            lane_center_x=line_center,
            frame_center_x=frame_center,
            line_count=len(line_positions),
            reason=reason,
        )

    def draw_debug(self, frame, mask, result: LaneDetectionResult) -> None:
        height, width = frame.shape[:2]

        # Camera center line.
        cv2.line(
            frame,
            (result.frame_center_x, 0),
            (result.frame_center_x, height),
            (255, 0, 255),
            2,
        )

        # Detected white-line center.
        if result.lane_center_x is not None:
            cv2.line(
                frame,
                (result.lane_center_x, 0),
                (result.lane_center_x, height),
                (0, 255, 255),
                2,
            )

        text = (
            f"dir={result.direction} conf={result.confidence} "
            f"lines={result.line_count} reason={result.reason}"
        )

        cv2.putText(
            frame,
            text,
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            2,
        )

        # Small white-mask preview in the top-right corner.
        mask_preview = cv2.resize(mask, (160, 120))
        mask_preview_bgr = cv2.cvtColor(mask_preview, cv2.COLOR_GRAY2BGR)
        frame[40:160, width - 170:width - 10] = mask_preview_bgr
