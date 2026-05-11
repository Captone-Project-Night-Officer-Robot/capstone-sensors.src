from __future__ import annotations

from dataclasses import dataclass

from raspbot.config import GPIOConfig


@dataclass(frozen=True)
class IRReading:
    left_detected: bool
    right_detected: bool
    raw_left: int
    raw_right: int


class IRSensors:
    """Left/right IR obstacle sensors.

    The original code treats GPIO value 0 as obstacle detected.
    """

    def __init__(self, config: GPIOConfig | None = None):
        self.config = config or GPIOConfig()

        try:
            import RPi.GPIO as GPIO
        except Exception as exc:
            raise RuntimeError("RPi.GPIO is required on Raspberry Pi hardware.") from exc

        self.GPIO = GPIO
        self.GPIO.setmode(self.GPIO.BOARD)
        self.GPIO.setwarnings(False)

        self.GPIO.setup(self.config.left_ir_pin, self.GPIO.IN)
        self.GPIO.setup(self.config.right_ir_pin, self.GPIO.IN)
        self.GPIO.setup(self.config.ir_enable_pin, self.GPIO.OUT)
        self.GPIO.output(self.config.ir_enable_pin, self.GPIO.HIGH)

    def read(self) -> IRReading:
        left = self.GPIO.input(self.config.left_ir_pin)
        right = self.GPIO.input(self.config.right_ir_pin)

        return IRReading(
            left_detected=(left == 0),
            right_detected=(right == 0),
            raw_left=left,
            raw_right=right,
        )
