"""
Motor driver for the Yahboom Raspbot (STM8 @ I2C 0x16 -> AT8236 -> motors).

The Raspbot's motor driver is NOT wired to Raspberry Pi GPIO pins. The Pi
talks to an STM8 MCU over I2C, which in turn drives the AT8236 H-bridge.
We delegate to Yahboom's library YB_Pcb_Car.py — drop it next to this file
(raspbot/hardware/YB_Pcb_Car.py) or install it where Python can import it.
"""

from __future__ import annotations

import time
from typing import Callable, Optional

import raspbot.config as cfg


class MotorDriverError(RuntimeError):
    pass


def _scale_speed(speed: int) -> int:
    speed = max(0, min(100, int(speed)))
    return int(round(speed * 255 / 100))


# Observer signature: (left_mu_signed, right_mu_signed). Both in motor units
# (-100..+100); +forward, -backward. Reports intended physical wheel motion.
MotorObserver = Callable[[float, float], None]


class MotorController:
    def __init__(self, dry_run: bool = False) -> None:
        self.dry_run = dry_run
        self.car = None
        self._observer: Optional[MotorObserver] = None

        if self.dry_run:
            print("[motor] DRY-RUN: motors will not move.")
            return

        try:
            from raspbot.hardware import YB_Pcb_Car  # type: ignore
        except Exception as exc:
            raise MotorDriverError(
                "YB_Pcb_Car library not found.\n"
                "Place YB_Pcb_Car.py at raspbot/hardware/YB_Pcb_Car.py."
            ) from exc

        self.car = YB_Pcb_Car.YB_Pcb_Car()
        self.stop()

    def set_observer(self, observer: Optional[MotorObserver]) -> None:
        """Register a callback fired with the *intended physical* wheel
        speeds (left, right) in signed motor units on every motor command.
        Used by the odometer to integrate dead-reckoning pose.
        """
        self._observer = observer

    def _notify(self, left_mu: float, right_mu: float) -> None:
        if self._observer is None:
            return
        try:
            self._observer(left_mu, right_mu)
        except Exception:
            # Telemetry must never break the control loop.
            pass

    def forward(self, speed: int) -> None:
        self._notify(speed, speed)
        if cfg.INVERT_FORWARD:
            return self._raw_back(speed)
        self._raw_forward(speed)

    def back(self, speed: int) -> None:
        self._notify(-speed, -speed)
        if cfg.INVERT_FORWARD:
            return self._raw_forward(speed)
        self._raw_back(speed)

    def forward_no_invert(self, speed: int) -> None:
        # Direct hardware-forward command, no logical inversion applied.
        # Caller is asserting "make the wheels spin in the Car_Run direction".
        self._notify(speed, speed)
        self._raw_forward(speed)

    def back_no_invert(self, speed: int) -> None:
        self._notify(-speed, -speed)
        self._raw_back(speed)

    def _raw_forward(self, speed: int) -> None:
        s = _scale_speed(speed)
        if self.dry_run:
            print(f"[motor] forward speed={speed} (raw={s})")
            return
        assert self.car is not None
        self.car.Car_Run(s, s)

    def _raw_back(self, speed: int) -> None:
        s = _scale_speed(speed)
        if self.dry_run:
            print(f"[motor] back speed={speed} (raw={s})")
            return
        assert self.car is not None
        self.car.Car_Back(s, s)

    def spin_left(self, speed: int) -> None:
        self._notify(-speed, speed)
        if cfg.INVERT_STEERING:
            return self.spin_right_no_invert(speed, _notify=False)
        self.spin_left_no_invert(speed, _notify=False)

    def spin_right(self, speed: int) -> None:
        self._notify(speed, -speed)
        if cfg.INVERT_STEERING:
            return self.spin_left_no_invert(speed, _notify=False)
        self.spin_right_no_invert(speed, _notify=False)

    def differential(self, left_speed: int, right_speed: int) -> None:
        """Drive both wheels forward at independent speeds (smooth steering)."""
        # Both wheels are always commanded *forward* here — the INVERT_FORWARD
        # branch below compensates by calling Car_Back when wiring is reversed,
        # so the resulting physical motion stays forward at (L, R).
        self._notify(left_speed, right_speed)

        if cfg.INVERT_STEERING:
            left_speed, right_speed = right_speed, left_speed

        sl = _scale_speed(left_speed)
        sr = _scale_speed(right_speed)

        if self.dry_run:
            print(f"[motor] differential L={left_speed} R={right_speed}")
            return

        assert self.car is not None
        if cfg.INVERT_FORWARD:
            self.car.Car_Back(sl, sr)
        else:
            self.car.Car_Run(sl, sr)

    def spin_left_no_invert(self, speed: int, _notify: bool = True) -> None:
        if _notify:
            self._notify(-speed, speed)
        s = _scale_speed(speed)
        if self.dry_run:
            print(f"[motor] spin_left speed={speed} (raw={s})")
            return
        assert self.car is not None
        if hasattr(self.car, "Car_Spin_Left"):
            self.car.Car_Spin_Left(s, s)
        else:
            self.car.Car_Left(s, s)

    def spin_right_no_invert(self, speed: int, _notify: bool = True) -> None:
        if _notify:
            self._notify(speed, -speed)
        s = _scale_speed(speed)
        if self.dry_run:
            print(f"[motor] spin_right speed={speed} (raw={s})")
            return
        assert self.car is not None
        if hasattr(self.car, "Car_Spin_Right"):
            self.car.Car_Spin_Right(s, s)
        else:
            self.car.Car_Right(s, s)

    def stop(self) -> None:
        self._notify(0, 0)
        if self.dry_run:
            print("[motor] stop")
            return
        assert self.car is not None
        self.car.Car_Stop()

    def cleanup(self) -> None:
        if self.dry_run:
            return
        try:
            self.stop()
            time.sleep(0.05)
            if self.car is not None:
                del self.car
                self.car = None
        except Exception as exc:
            print(f"[motor] cleanup warning: {exc}")

    def safe_stop(self) -> None:
        self.cleanup()
