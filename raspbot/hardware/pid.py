"""
Simple PID controller.

Used by the line-follower to convert a pixel offset (line center − frame center)
into a steering correction. Operates at a roughly fixed sample rate (set by
CONTROL_DELAY_SEC), so the derivative term is a plain difference rather than
a time-divided derivative — matches Yahboom's convention.
"""

from __future__ import annotations


class PIDController:
    def __init__(
        self,
        kp: float,
        ki: float,
        kd: float,
        output_limit: float | None = None,
        integral_limit: float | None = None,
    ) -> None:
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.output_limit = output_limit
        self.integral_limit = integral_limit
        self._integral = 0.0
        self._prev_error: float | None = None

    def reset(self) -> None:
        self._integral = 0.0
        self._prev_error = None

    def update(self, error: float) -> float:
        p = self.kp * error

        self._integral += error
        if self.integral_limit is not None:
            limit = self.integral_limit
            if self._integral > limit:
                self._integral = limit
            elif self._integral < -limit:
                self._integral = -limit
        i = self.ki * self._integral

        if self._prev_error is None:
            d = 0.0
        else:
            d = self.kd * (error - self._prev_error)

        output = p + i + d

        if self.output_limit is not None:
            limit = self.output_limit
            if output > limit:
                output = limit
            elif output < -limit:
                output = -limit

        self._prev_error = error
        return output
