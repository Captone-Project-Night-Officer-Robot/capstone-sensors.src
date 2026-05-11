from __future__ import annotations

import argparse
import time

from raspbot.config import AppConfig
from raspbot.hardware import MotorControl, MockMotorControl


def main() -> None:
    parser = argparse.ArgumentParser(description="Test Raspbot motors.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--speed", type=int, default=35)
    parser.add_argument("--seconds", type=float, default=0.8)
    args = parser.parse_args()

    config = AppConfig()
    motor = MockMotorControl(config.motor) if args.dry_run else MotorControl(config.motor)

    try:
        print("Forward")
        motor.move_forward(args.speed)
        time.sleep(args.seconds)

        print("Stop")
        motor.stop()
        time.sleep(0.4)

        print("Steer left")
        motor.steer_left(args.speed)
        time.sleep(args.seconds)

        print("Stop")
        motor.stop()
        time.sleep(0.4)

        print("Steer right")
        motor.steer_right(args.speed)
        time.sleep(args.seconds)

        print("Stop")
        motor.stop()
        time.sleep(0.4)

        print("Spin left")
        motor.spin_left(args.speed)
        time.sleep(args.seconds)

        print("Stop")
        motor.stop()
        time.sleep(0.4)

        print("Spin right")
        motor.spin_right(args.speed)
        time.sleep(args.seconds)

    finally:
        motor.stop()
        print("Motor test finished.")


if __name__ == "__main__":
    main()
