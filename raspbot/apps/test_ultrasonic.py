from __future__ import annotations

import time

from raspbot.config import AppConfig
from raspbot.hardware import UltrasonicSensor


def main() -> None:
    config = AppConfig()
    sensor = UltrasonicSensor(config.gpio, config.navigation)

    print("Ultrasonic test. Press Ctrl+C to stop.")

    try:
        while True:
            distance = sensor.measure_cm()
            print(f"distance_cm={distance:.2f}")
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
