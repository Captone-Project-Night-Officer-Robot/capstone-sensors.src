"""
Minimal direct-GPIO motor test. Bypasses raspbot.* entirely.

Drives both motors forward for 2 seconds at full duty.
If wheels do not move, the issue is hardware (battery switch off,
flat battery, loose wire, or driver board), not Python code.
"""

from __future__ import annotations

import time

import RPi.GPIO as GPIO  # type: ignore


IN1, IN2, IN3, IN4 = 20, 21, 19, 26
ENA, ENB = 16, 13


def main() -> None:
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    for pin in (IN1, IN2, IN3, IN4, ENA, ENB):
        GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)

    pwm_a = GPIO.PWM(ENA, 2000)
    pwm_b = GPIO.PWM(ENB, 2000)
    pwm_a.start(100)
    pwm_b.start(100)

    try:
        print("[raw] forward 2s")
        GPIO.output(IN1, GPIO.HIGH)
        GPIO.output(IN2, GPIO.LOW)
        GPIO.output(IN3, GPIO.HIGH)
        GPIO.output(IN4, GPIO.LOW)
        time.sleep(2.0)

        print("[raw] stop")
        GPIO.output(IN1, GPIO.LOW)
        GPIO.output(IN2, GPIO.LOW)
        GPIO.output(IN3, GPIO.LOW)
        GPIO.output(IN4, GPIO.LOW)
        pwm_a.ChangeDutyCycle(0)
        pwm_b.ChangeDutyCycle(0)
        time.sleep(0.2)
    finally:
        pwm_a.stop()
        pwm_b.stop()
        GPIO.cleanup()
        print("[raw] done")


if __name__ == "__main__":
    main()
