"""
HC-SR04 ultrasonic distance sensor.

Sampling is done in a background thread so the main control loop never blocks
on the echo timeout. The main loop reads `latest_cm()` (median of last few
samples) — non-blocking and lock-protected.
"""

from __future__ import annotations

import math
import statistics
import threading
import time

import raspbot.config as cfg


_SAMPLE_WINDOW = 3


class UltrasonicSensor:
    def __init__(self, simulate: bool = False) -> None:
        self.simulate = simulate
        self._samples: list[float] = []
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._gpio = None

        if simulate:
            return

        try:
            import RPi.GPIO as GPIO  # type: ignore
        except Exception as exc:
            raise RuntimeError(
                "RPi.GPIO not available. Run on the Pi, or pass simulate=True."
            ) from exc

        self._gpio = GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(cfg.ULTRASONIC_TRIG, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(cfg.ULTRASONIC_ECHO, GPIO.IN)

    def start(self) -> None:
        if self._thread is not None:
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None

    def latest_cm(self) -> float:
        with self._lock:
            valid = [s for s in self._samples if math.isfinite(s)]

        if not valid:
            return math.inf

        return statistics.median(valid)

    def cleanup(self) -> None:
        self.stop()

    def _measure_once(self) -> float:
        if self.simulate or self._gpio is None:
            return math.inf

        GPIO = self._gpio
        GPIO.output(cfg.ULTRASONIC_TRIG, False)
        time.sleep(0.000002)
        GPIO.output(cfg.ULTRASONIC_TRIG, True)
        time.sleep(0.000015)
        GPIO.output(cfg.ULTRASONIC_TRIG, False)

        t_start_wait = time.time()
        while not GPIO.input(cfg.ULTRASONIC_ECHO):
            if time.time() - t_start_wait > cfg.ULTRASONIC_TIMEOUT_SEC:
                return math.inf

        t_rising = time.time()
        while GPIO.input(cfg.ULTRASONIC_ECHO):
            if time.time() - t_rising > cfg.ULTRASONIC_TIMEOUT_SEC:
                return math.inf

        t_falling = time.time()
        cm = (t_falling - t_rising) * 340.0 / 2.0 * 100.0

        if cm < cfg.ULTRASONIC_MIN_CM or cm > cfg.ULTRASONIC_MAX_CM:
            return math.inf

        return cm

    def _poll_loop(self) -> None:
        interval = 1.0 / max(1, cfg.ULTRASONIC_POLL_HZ)

        while not self._stop_event.is_set():
            cm = self._measure_once()

            with self._lock:
                self._samples.append(cm)
                if len(self._samples) > _SAMPLE_WINDOW:
                    self._samples.pop(0)

            self._stop_event.wait(interval)
