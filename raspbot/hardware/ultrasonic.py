from __future__ import annotations

import time

from raspbot.config import GPIOConfig, NavigationConfig


class UltrasonicSensor:
    """HC-SR04-style ultrasonic distance sensor."""

    def __init__(
        self,
        gpio_config: GPIOConfig | None = None,
        navigation_config: NavigationConfig | None = None,
    ):
        self.gpio_config = gpio_config or GPIOConfig()
        self.navigation_config = navigation_config or NavigationConfig()

        try:
            import RPi.GPIO as GPIO
        except Exception as exc:
            raise RuntimeError("RPi.GPIO is required on Raspberry Pi hardware.") from exc

        self.GPIO = GPIO
        self.GPIO.setmode(self.GPIO.BOARD)
        self.GPIO.setwarnings(False)
        self.GPIO.setup(self.gpio_config.trig_pin, self.GPIO.OUT)
        self.GPIO.setup(self.gpio_config.echo_pin, self.GPIO.IN)

    def measure_cm(self, samples: int = 3, timeout_sec: float = 0.03) -> float:
        readings: list[float] = []

        for _ in range(samples):
            value = self._single_measure_cm(timeout_sec=timeout_sec)
            if 0 < value < self.navigation_config.max_valid_distance_cm:
                readings.append(value)

        if not readings:
            return -1.0

        return sum(readings) / len(readings)

    def _single_measure_cm(self, timeout_sec: float = 0.03) -> float:
        gpio = self.GPIO

        gpio.output(self.gpio_config.trig_pin, gpio.LOW)
        time.sleep(0.000002)

        gpio.output(self.gpio_config.trig_pin, gpio.HIGH)
        time.sleep(0.000015)

        gpio.output(self.gpio_config.trig_pin, gpio.LOW)

        start_wait = time.time()
        while not gpio.input(self.gpio_config.echo_pin):
            if time.time() - start_wait > timeout_sec:
                return -1.0

        pulse_start = time.time()

        while gpio.input(self.gpio_config.echo_pin):
            if time.time() - pulse_start > timeout_sec:
                return -1.0

        pulse_end = time.time()

        return ((pulse_end - pulse_start) * 340.0 / 2.0) * 100.0
