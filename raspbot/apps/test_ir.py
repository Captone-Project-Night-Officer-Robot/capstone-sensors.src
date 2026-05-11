from __future__ import annotations

import time

from raspbot.config import AppConfig
from raspbot.hardware import IRSensors


def main() -> None:
    config = AppConfig()
    sensors = IRSensors(config.gpio)

    print("IR sensor test. GPIO raw 0 means obstacle detected. Press Ctrl+C to stop.")

    try:
        while True:
            reading = sensors.read()
            print(
                f"left_detected={reading.left_detected} raw_left={reading.raw_left} | "
                f"right_detected={reading.right_detected} raw_right={reading.raw_right}"
            )
            time.sleep(0.2)

    except KeyboardInterrupt:
        print("\nStopped.")

    finally:
        try:
            import RPi.GPIO as GPIO
            GPIO.cleanup()
        except Exception:
            pass


if __name__ == "__main__":
    main()
