"""
Main app: follow a white line using Raspberry Pi camera, with ultrasonic + IR
obstacle avoidance as an override layer.

Examples:

Pi camera:
    python -m raspbot.apps.line_follow --camera picamera2

USB camera:
    python -m raspbot.apps.line_follow --camera usb --camera-index 0

Safe debug mode, no motor movement:
    python -m raspbot.apps.line_follow --camera picamera2 --dry-run --debug

Disable obstacle avoidance (sensors not wired yet):
    python -m raspbot.apps.line_follow --camera picamera2 --no-avoidance
"""

from __future__ import annotations

import argparse
import os
import time

import cv2

import raspbot.config as cfg
from raspbot.hardware.avoider import Avoider
from raspbot.hardware.motor import MotorController
from raspbot.vision.camera import create_camera
from raspbot.vision.white_line_detector import WhiteLineDetector, draw_debug


def _display_available() -> bool:
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def _gpio_cleanup() -> None:
    try:
        import RPi.GPIO as GPIO  # type: ignore
        GPIO.cleanup()
    except Exception:
        pass


def decide_action(found: bool, offset_x: int | None) -> str:
    if not found or offset_x is None:
        return "lost"

    if abs(offset_x) <= cfg.CENTER_TOLERANCE_PX:
        return "forward"

    if offset_x < 0:
        return "left"

    return "right"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--camera", choices=["picamera2", "usb"], default="picamera2")
    parser.add_argument("--camera-index", type=int, default=cfg.USB_CAMERA_INDEX)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--no-avoidance",
        action="store_true",
        help="Disable ultrasonic + IR obstacle avoidance.",
    )
    args = parser.parse_args()

    camera = create_camera(
        camera_type=args.camera,
        index=args.camera_index,
        width=cfg.CAMERA_WIDTH,
        height=cfg.CAMERA_HEIGHT,
        fps=cfg.CAMERA_FPS,
    )

    motor = MotorController(dry_run=args.dry_run)
    detector = WhiteLineDetector()

    avoider: Avoider | None = None
    if cfg.AVOIDANCE_ENABLED and not args.no_avoidance:
        try:
            avoider = Avoider(simulate=args.dry_run)
            print("[app] Obstacle avoidance enabled.")
        except Exception as exc:
            print(f"[app] WARNING: avoidance disabled ({exc})")
            avoider = None
    else:
        print("[app] Obstacle avoidance OFF.")

    print("[app] White-line follower started.")
    print("[app] Stop with Ctrl+C.")

    if args.debug:
        print("[app] Debug mode enabled. Press q to quit.")

    frame_idx = 0
    has_display = args.debug and _display_available()

    try:
        while True:
            frame = camera.read()

            if avoider is not None:
                decision = avoider.evaluate()

                if decision.blocked:
                    if args.debug:
                        print(
                            f"[avoid] BLOCKED dist={decision.distance_cm:.1f}cm "
                            f"ir=(L={decision.ir.left_blocked},"
                            f"R={decision.ir.right_blocked}) "
                            f"reason={decision.reason} -> spin {decision.direction}"
                        )
                    avoider.execute(motor, decision)
                    frame_idx += 1
                    continue

            detection = detector.detect(frame)

            action = decide_action(detection.found, detection.offset_x)

            if action == "forward":
                motor.forward(cfg.FORWARD_SPEED)
            elif action == "left":
                motor.spin_left(cfg.TURN_SPEED)
            elif action == "right":
                motor.spin_right(cfg.TURN_SPEED)
            else:
                if cfg.STOP_WHEN_LINE_LOST:
                    motor.stop()
                else:
                    motor.spin_left(cfg.SEARCH_TURN_SPEED)

            if args.debug and frame_idx % 15 == 0:
                print(
                    f"[app] frame={frame_idx} found={detection.found} "
                    f"offset={detection.offset_x} area={int(detection.area)} "
                    f"action={action}"
                )

            if has_display:
                debug = draw_debug(frame, detection)

                cv2.imshow("vision-test", debug)
                cv2.imshow("white-line-mask", detection.mask)

                key = cv2.waitKey(1) & 0xFF

                if key == ord("q"):
                    break

            frame_idx += 1
            time.sleep(cfg.CONTROL_DELAY_SEC)

    except KeyboardInterrupt:
        print("\n[app] Ctrl+C received. Stopping.")
    finally:
        if avoider is not None:
            avoider.cleanup()
        motor.safe_stop()
        camera.release()
        cv2.destroyAllWindows()
        _gpio_cleanup()
        print("[app] Done.")


if __name__ == "__main__":
    main()
