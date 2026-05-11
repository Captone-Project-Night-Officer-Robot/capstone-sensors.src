"""Local motor driver location.

IMPORTANT:
This file is included so the project no longer needs YB_PCB_CAR_PATH or .env.

If your Yahboom/Raspbot kit provides the official driver file, replace THIS file
with the official `YB_Pcb_Car.py`.

Required public API:
    class YB_Pcb_Car:
        Car_Run(left_speed, right_speed)
        Car_Back(left_speed, right_speed)
        Car_Spin_Left(left_speed, right_speed)
        Car_Spin_Right(left_speed, right_speed)
        Car_Stop()

This fallback intentionally does not move motors because the actual motor HAT
pin/PWM mapping was not available in the provided files.
"""


class YB_Pcb_Car:
    def __init__(self):
        raise RuntimeError(
            "Local placeholder motor driver is installed, but it cannot drive real motors. "
            "Replace robot_side/motor_driver/YB_Pcb_Car.py with the official Yahboom/Raspbot "
            "YB_Pcb_Car.py driver for your motor board. No .env path is needed after that."
        )

    def Car_Run(self, left_speed, right_speed):
        raise NotImplementedError

    def Car_Back(self, left_speed, right_speed):
        raise NotImplementedError

    def Car_Spin_Left(self, left_speed, right_speed):
        raise NotImplementedError

    def Car_Spin_Right(self, left_speed, right_speed):
        raise NotImplementedError

    def Car_Stop(self):
        raise NotImplementedError
