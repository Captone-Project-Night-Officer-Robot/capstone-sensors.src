"""
Standalone obstacle-sensor test. No motors.

Prints ultrasonic distance + IR state at 5 Hz so you can confirm wiring
before running the full line_follow app.

Usage:
    python -m scripts.avoid_test
"""

from __future__ import annotations

import time

import raspbot.config as cfg
from raspbot.hardware.ir_sensors import IRSensors
from raspbot.hardware.ultrasonic import UltrasonicSensor


def _gpio_cleanup() -> None:
    try:
        import RPi.GPIO as GPIO  # type: ignore
        GPIO.cleanup()
    except Exception:
        pass


def main() -> None:
    ultrasonic = UltrasonicSensor()
    ir = IRSensors()
    ultrasonic.start()

    print(
        f"Sampling sensors. AVOID_DISTANCE_CM={cfg.AVOID_DISTANCE_CM}. "
        "Ctrl+C to stop."
    )

    try:
        while True:
            cm = ultrasonic.latest_cm()
            r = ir.read()
            cm_str = "  inf" if cm == float("inf") else f"{cm:6.1f}"
            flag = "BLOCKED" if (cm < cfg.AVOID_DISTANCE_CM or r.any_blocked) else "clear  "
            print(
                f"{flag}  distance={cm_str} cm   "
                f"IR L={int(r.left_blocked)} R={int(r.right_blocked)}"
            )
            time.sleep(0.2)
    except KeyboardInterrupt:
        print()
    finally:
        ultrasonic.cleanup()
        _gpio_cleanup()


if __name__ == "__main__":
    main()
