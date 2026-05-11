from __future__ import annotations

import argparse
import time

import cv2

from raspbot.config import AppConfig, MotorConfig, NavigationConfig
from raspbot.hardware import IRSensors, MotorControl, MockMotorControl, PiCamera, UltrasonicSensor
from raspbot.navigation import LineFollowerController
from raspbot.vision import GreenLaneDetector


def parse_args():
    parser = argparse.ArgumentParser(description="Run Raspberry Pi RC car line follower.")

    parser.add_argument("--dry-run", action="store_true", help="Do not move real motors.")
    parser.add_argument("--show", action="store_true", help="Show OpenCV debug window.")
    parser.add_argument("--no-window", action="store_true", help="Disable OpenCV debug window.")

    parser.add_argument("--forward-speed", type=int, default=None)
    parser.add_argument("--turn-speed", type=int, default=None)
    parser.add_argument("--slow-speed", type=int, default=None)

    parser.add_argument("--emergency-stop-cm", type=float, default=None)
    parser.add_argument("--caution-cm", type=float, default=None)

    parser.add_argument("--disable-ir", action="store_true", help="Run without IR side obstacle sensors.")
    parser.add_argument("--disable-ultrasonic", action="store_true", help="Run without ultrasonic front sensor.")

    return parser.parse_args()


def build_config(args) -> AppConfig:
    base = AppConfig()

    motor = MotorConfig(
        yb_pcb_car_path=base.motor.yb_pcb_car_path,
        forward_speed=args.forward_speed if args.forward_speed is not None else base.motor.forward_speed,
        turn_speed=args.turn_speed if args.turn_speed is not None else base.motor.turn_speed,
        slow_speed=args.slow_speed if args.slow_speed is not None else base.motor.slow_speed,
        max_speed=base.motor.max_speed,
    )

    navigation = NavigationConfig(
        emergency_stop_cm=args.emergency_stop_cm if args.emergency_stop_cm is not None else base.navigation.emergency_stop_cm,
        caution_cm=args.caution_cm if args.caution_cm is not None else base.navigation.caution_cm,
        max_valid_distance_cm=base.navigation.max_valid_distance_cm,
        no_lane_behavior=base.navigation.no_lane_behavior,
        control_loop_sleep_sec=base.navigation.control_loop_sleep_sec,
    )

    return AppConfig(
        gpio=base.gpio,
        camera=base.camera,
        motor=motor,
        lane=base.lane,
        navigation=navigation,
    )


def main() -> None:
    args = parse_args()
    config = build_config(args)

    show_window = args.show and not args.no_window

    motor = MockMotorControl(config.motor) if args.dry_run else MotorControl(config.motor)
    camera = PiCamera(config.camera)
    detector = GreenLaneDetector(config.lane)
    controller = LineFollowerController(motor, config)

    ir_sensors = None if args.disable_ir else IRSensors(config.gpio)
    ultrasonic = None if args.disable_ultrasonic else UltrasonicSensor(config.gpio, config.navigation)

    print("Raspbot line follower starting.")
    print(f"dry_run={args.dry_run}, show_window={show_window}")
    print("Press Ctrl+C or 'q' in the debug window to stop.")

    camera.start()

    try:
        while True:
            distance_cm = -1.0 if ultrasonic is None else ultrasonic.measure_cm()
            ir_reading = None if ir_sensors is None else ir_sensors.read()

            frame = camera.read_bgr()
            lane_result, debug_frame = detector.detect(frame)

            telemetry = controller.decide(distance_cm, ir_reading, lane_result)
            controller.apply(telemetry)

            print(
                f"action={telemetry.action:<13} reason={telemetry.reason:<32} "
                f"dist={telemetry.distance_cm:>6.1f}cm "
                f"ir=({int(telemetry.ir_left_detected)}, {int(telemetry.ir_right_detected)}) "
                f"lane={telemetry.lane_direction:<8} conf={telemetry.lane_confidence:.2f} "
                f"motor=({telemetry.left_motor_speed}, {telemetry.right_motor_speed})"
            )

            if show_window:
                cv2.imshow("Raspbot Line Follower", debug_frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            time.sleep(config.navigation.control_loop_sleep_sec)

    except KeyboardInterrupt:
        print("\nInterrupted by user.")

    finally:
        print("Stopping robot and cleaning up.")
        motor.stop()
        camera.stop()
        cv2.destroyAllWindows()

        try:
            import RPi.GPIO as GPIO
            GPIO.cleanup()
        except Exception:
            pass


if __name__ == "__main__":
    main()
