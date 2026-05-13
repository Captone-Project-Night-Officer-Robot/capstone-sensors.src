"""
Motor test.

Put the car on a stand before running.
"""

import time

import raspbot.config as cfg
from raspbot.hardware.motor import MotorController


def main() -> None:
    motor = MotorController(dry_run=False)

    try:
        print("Forward")
        motor.forward(cfg.FORWARD_SPEED)
        time.sleep(0.7)

        print("Stop")
        motor.stop()
        time.sleep(0.3)

        print("Spin left")
        motor.spin_left(cfg.TURN_SPEED)
        time.sleep(0.5)

        print("Stop")
        motor.stop()
        time.sleep(0.3)

        print("Spin right")
        motor.spin_right(cfg.TURN_SPEED)
        time.sleep(0.5)

        print("Stop")
        motor.stop()
        time.sleep(0.3)

        print("Back")
        motor.back(cfg.TURN_SPEED)
        time.sleep(0.5)

    finally:
        print("Final stop")
        motor.safe_stop()


if __name__ == "__main__":
    main()
