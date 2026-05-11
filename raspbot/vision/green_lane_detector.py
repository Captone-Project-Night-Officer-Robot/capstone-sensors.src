from __future__ import annotations

from typing import Tuple

import cv2
import numpy as np

from raspbot.config import LaneConfig
from raspbot.vision.types import LaneDetectionResult


class GreenLaneDetector:
    """Green HSV mask + ROI + Hough line based lane detector."""

    def __init__(self, config: LaneConfig | None = None):
        self.config = config or LaneConfig()

    def detect(self, frame_bgr) -> tuple[LaneDetectionResult, object]:
        mask = self.apply_green_mask(frame_bgr)
        roi_mask = self.apply_roi(mask)
        debug_frame, line_positions = self.detect_lines(roi_mask, frame_bgr)
        result = self.navigate_from_lines(line_positions, frame_bgr.shape[1])
        self.draw_debug(debug_frame, result)
        return result, debug_frame

    def apply_green_mask(self, image_bgr):
        hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)

        lower_green = np.array([
            self.config.lower_green_h,
            self.config.lower_green_s,
            self.config.lower_green_v,
        ])
        upper_green = np.array([
            self.config.upper_green_h,
            self.config.upper_green_s,
            self.config.upper_green_v,
        ])

        mask = cv2.inRange(hsv, lower_green, upper_green)

        kernel_size = self.config.morphology_kernel_size
        kernel = np.ones((kernel_size, kernel_size), np.uint8)

        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        return mask

    def apply_roi(self, mask):
        height, width = mask.shape

        top = int(height * self.config.roi_top_ratio)

        outer_polygon = np.array([[
            (0, height),
            (width, height),
            (int(width * self.config.roi_right_top_ratio), top),
            (int(width * self.config.roi_left_top_ratio), top),
        ]])

        cutout_left = int(width * self.config.center_cutout_left_ratio)
        cutout_right = int(width * self.config.center_cutout_right_ratio)
        inner_cutout = np.array([[
            (cutout_left, top),
            (cutout_right, top),
            (cutout_right, height),
            (cutout_left, height),
        ]])

        roi = np.zeros_like(mask)
        cv2.fillPoly(roi, outer_polygon, 255)
        cv2.fillPoly(roi, inner_cutout, 0)

        return cv2.bitwise_and(mask, roi)

    def detect_lines(self, mask, original_frame):
        theta = np.pi / self.config.hough_theta_divisor

        lines = cv2.HoughLinesP(
            mask,
            self.config.hough_rho,
            theta,
            self.config.hough_threshold,
            minLineLength=self.config.hough_min_line_length,
            maxLineGap=self.config.hough_max_line_gap,
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

        if len(line_positions) < self.config.min_lines_required:
            return LaneDetectionResult(
                direction="no_line",
                confidence=0.0,
                lane_center_x=None,
                frame_center_x=frame_center,
                line_count=len(line_positions),
                reason="not_enough_lines",
            )

        sorted_lines = sorted(line_positions, key=lambda p: p[0])
        left_line = sorted_lines[0]
        right_line = sorted_lines[-1]

        lane_center = (left_line[0] + right_line[0]) // 2
        offset = lane_center - frame_center
        abs_offset = abs(offset)

        if abs_offset <= self.config.lane_center_tolerance_px:
            direction = "straight"
            reason = "lane_centered"
        elif offset < 0:
            direction = "left"
            reason = "lane_center_left_of_frame_center"
        else:
            direction = "right"
            reason = "lane_center_right_of_frame_center"

        line_score = min(1.0, len(line_positions) / 6.0)
        offset_score = max(0.0, 1.0 - (abs_offset / max(frame_width / 2, 1)))
        confidence = round((line_score * 0.6) + (offset_score * 0.4), 3)

        return LaneDetectionResult(
            direction=direction,
            confidence=confidence,
            lane_center_x=lane_center,
            frame_center_x=frame_center,
            line_count=len(line_positions),
            reason=reason,
        )

    def draw_debug(self, frame, result: LaneDetectionResult) -> None:
        h, _ = frame.shape[:2]
        cv2.line(frame, (result.frame_center_x, 0), (result.frame_center_x, h), (255, 0, 255), 2)

        if result.lane_center_x is not None:
            cv2.line(frame, (result.lane_center_x, 0), (result.lane_center_x, h), (0, 255, 255), 2)

        text = (
            f"dir={result.direction} conf={result.confidence} "
            f"lines={result.line_count} reason={result.reason}"
        )
        cv2.putText(frame, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)
