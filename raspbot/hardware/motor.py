"""
Direct GPIO motor driver for Yahboom Raspberry Pi 4WD car.

This project does not import official CarRun.py because some official demo files
may execute movement code when run/imported.

Pin layout is based on Yahboom official 4.Code/python/CarRun.py:

    IN1 = 20
    IN2 = 21
    IN3 = 19
    IN4 = 26
    ENA = 16
    ENB = 13
"""

from __future__ import annotations

import time

import raspbot.config as cfg


class MotorDriverError(RuntimeError):
    pass


class MotorController:
    def __init__(self, dry_run: bool = False) -> None:
        self.dry_run = dry_run
        self.GPIO = None
        self.pwm_ena = None
        self.pwm_enb = None

        if self.dry_run:
            print("[motor] DRY-RUN: motors will not move.")
            return

        try:
            import RPi.GPIO as GPIO  # type: ignore
        except Exception as exc:
            raise MotorDriverError(
                "RPi.GPIO is not installed or code is not running on Raspberry Pi.\n"
                "Install it with:\n"
                "  sudo apt install -y python3-rpi.gpio\n"
            ) from exc

        self.GPIO = GPIO

        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)

        GPIO.setup(cfg.ENA, GPIO.OUT, initial=GPIO.HIGH)
        GPIO.setup(cfg.IN1, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(cfg.IN2, GPIO.OUT, initial=GPIO.LOW)

        GPIO.setup(cfg.ENB, GPIO.OUT, initial=GPIO.HIGH)
        GPIO.setup(cfg.IN3, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(cfg.IN4, GPIO.OUT, initial=GPIO.LOW)

        self.pwm_ena = GPIO.PWM(cfg.ENA, cfg.PWM_FREQUENCY)
        self.pwm_enb = GPIO.PWM(cfg.ENB, cfg.PWM_FREQUENCY)

        self.pwm_ena.start(0)
        self.pwm_enb.start(0)

        self.stop()

    def _clip_speed(self, speed: int) -> int:
        return max(0, min(100, int(speed)))

    def _set_speed(self, left_speed: int, right_speed: int) -> None:
        if self.dry_run:
            return

        assert self.pwm_ena is not None
        assert self.pwm_enb is not None

        self.pwm_ena.ChangeDutyCycle(self._clip_speed(left_speed))
        self.pwm_enb.ChangeDutyCycle(self._clip_speed(right_speed))

    def _write_pins(self, in1: int, in2: int, in3: int, in4: int) -> None:
        if self.dry_run:
            print(f"[motor] pins IN1={in1} IN2={in2} IN3={in3} IN4={in4}")
            return

        assert self.GPIO is not None
        GPIO = self.GPIO

        GPIO.output(cfg.IN1, GPIO.HIGH if in1 else GPIO.LOW)
        GPIO.output(cfg.IN2, GPIO.HIGH if in2 else GPIO.LOW)
        GPIO.output(cfg.IN3, GPIO.HIGH if in3 else GPIO.LOW)
        GPIO.output(cfg.IN4, GPIO.HIGH if in4 else GPIO.LOW)

    def forward(self, speed: int) -> None:
        if cfg.INVERT_FORWARD:
            return self.back_no_invert(speed)

        if self.dry_run:
            print(f"[motor] forward speed={speed}")

        self._write_pins(1, 0, 1, 0)
        self._set_speed(speed, speed)

    def back(self, speed: int) -> None:
        if cfg.INVERT_FORWARD:
            return self.forward_no_invert(speed)

        self.back_no_invert(speed)

    def forward_no_invert(self, speed: int) -> None:
        if self.dry_run:
            print(f"[motor] forward speed={speed}")

        self._write_pins(1, 0, 1, 0)
        self._set_speed(speed, speed)

    def back_no_invert(self, speed: int) -> None:
        if self.dry_run:
            print(f"[motor] back speed={speed}")

        self._write_pins(0, 1, 0, 1)
        self._set_speed(speed, speed)

    def spin_left(self, speed: int) -> None:
        if cfg.INVERT_STEERING:
            return self.spin_right_no_invert(speed)

        self.spin_left_no_invert(speed)

    def spin_right(self, speed: int) -> None:
        if cfg.INVERT_STEERING:
            return self.spin_left_no_invert(speed)

        self.spin_right_no_invert(speed)

    def spin_left_no_invert(self, speed: int) -> None:
        if self.dry_run:
            print(f"[motor] spin_left speed={speed}")

        self._write_pins(0, 1, 1, 0)
        self._set_speed(speed, speed)

    def spin_right_no_invert(self, speed: int) -> None:
        if self.dry_run:
            print(f"[motor] spin_right speed={speed}")

        self._write_pins(1, 0, 0, 1)
        self._set_speed(speed, speed)

    def stop(self) -> None:
        if self.dry_run:
            print("[motor] stop")
            return

        self._write_pins(0, 0, 0, 0)
        self._set_speed(0, 0)

    def cleanup(self) -> None:
        if self.dry_run:
            return

        try:
            self.stop()
            time.sleep(0.05)

            if self.pwm_ena is not None:
                self.pwm_ena.stop()
            if self.pwm_enb is not None:
                self.pwm_enb.stop()

            if self.GPIO is not None:
                self.GPIO.cleanup()
        except Exception as exc:
            print(f"[motor] cleanup warning: {exc}")

    def safe_stop(self) -> None:
        self.cleanup()
