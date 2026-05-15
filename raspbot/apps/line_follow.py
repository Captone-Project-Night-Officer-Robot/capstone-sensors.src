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
from raspbot.hardware.ir_sensors import IRReading
from raspbot.hardware.motor import MotorController
from raspbot.hardware.pid import PIDController
from raspbot.vision.camera import create_camera
from raspbot.vision.fall_detector import FallDetectorClient
from raspbot.vision.mjpeg_server import MJPEGServer
from raspbot.vision.white_line_detector import WhiteLineDetector, draw_debug


steering_pid = PIDController(
    kp=cfg.STEERING_PID_KP,
    ki=cfg.STEERING_PID_KI,
    kd=cfg.STEERING_PID_KD,
    output_limit=cfg.STEERING_PID_OUTPUT_LIMIT,
    integral_limit=cfg.STEERING_PID_INTEGRAL_LIMIT,
)


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


class LostLineSearcher:
    """Sweeps right → left → right → left while the line is missing."""

    def __init__(self) -> None:
        self._direction = "right"
        self._phase_start: float | None = None

    def reset(self) -> None:
        self._direction = "right"
        self._phase_start = None

    def step(self, motor: MotorController) -> str:
        now = time.monotonic()

        if self._phase_start is None:
            self._phase_start = now
        elif now - self._phase_start >= cfg.SEARCH_SWEEP_SEC:
            self._direction = "left" if self._direction == "right" else "right"
            self._phase_start = now

        if self._direction == "right":
            motor.spin_right(cfg.SEARCH_TURN_SPEED)
        else:
            motor.spin_left(cfg.SEARCH_TURN_SPEED)

        return self._direction


def handle_lost_line(
    motor: MotorController,
    searcher: LostLineSearcher,
    avoider: Avoider | None,
) -> str:
    """Decide motion when the white line is not visible.

    Priority:
      1. If IR sensors report an obstacle, turn away from it.
      2. Otherwise, continue the left-right sweep search.
    """
    ir: IRReading = (
        avoider.read_ir() if (avoider is not None and cfg.IR_ENABLED)
        else IRReading(False, False)
    )

    if ir.left_blocked and ir.right_blocked:
        motor.spin_right(cfg.SEARCH_TURN_SPEED)
        return "ir-both -> spin right"

    if ir.left_blocked:
        motor.spin_right(cfg.SEARCH_TURN_SPEED)
        return "ir-left -> spin right"

    if ir.right_blocked:
        motor.spin_left(cfg.SEARCH_TURN_SPEED)
        return "ir-right -> spin left"

    return f"sweep -> spin {searcher.step(motor)}"


def steering_speeds(offset_x: int) -> tuple[int, int]:
    """PID-driven differential drive. Returns (left_speed, right_speed)."""
    base = cfg.FORWARD_SPEED
    deadband = cfg.CENTER_TOLERANCE_PX

    # Inside the deadband, drive straight but still feed 0 into the PID so the
    # derivative term doesn't see a discontinuity when we cross the boundary.
    error = 0.0 if abs(offset_x) <= deadband else float(offset_x)

    correction = int(steering_pid.update(error))

    if correction >= 0:
        # offset positive → line is right of center → slow RIGHT wheel.
        return (base, max(0, base - correction))

    # offset negative → line is left of center → slow LEFT wheel.
    return (max(0, base + correction), base)


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
    parser.add_argument(
        "--stream",
        action="store_true",
        help="Serve MJPEG of the debug view at http://<pi-ip>:<port>/",
    )
    parser.add_argument("--stream-port", type=int, default=8080)
    parser.add_argument("--stream-fps", type=int, default=15)
    parser.add_argument(
        "--fall-detection",
        action="store_true",
        help="Enable remote YOLO fall detection via the inference server.",
    )
    parser.add_argument("--fall-server", default=cfg.FALL_SERVER_URL)
    parser.add_argument(
        "--fall-camera-index", type=int, default=cfg.FALL_USB_CAMERA_INDEX
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
    searcher = LostLineSearcher()

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

    stream_server: MJPEGServer | None = None
    if args.stream:
        stream_server = MJPEGServer(
            port=args.stream_port, fps_cap=args.stream_fps
        )
        stream_server.start()
        print(
            f"[app] MJPEG stream live: open http://<pi-ip>:{args.stream_port}/ "
            "in a browser on your laptop."
        )

    fall_client: FallDetectorClient | None = None
    if args.fall_detection:
        try:
            fall_client = FallDetectorClient(
                server_url=args.fall_server,
                camera_index=args.fall_camera_index,
                camera_width=cfg.FALL_CAMERA_WIDTH,
                camera_height=cfg.FALL_CAMERA_HEIGHT,
                target_fps=cfg.FALL_TARGET_FPS,
                jpeg_quality=cfg.FALL_JPEG_QUALITY,
                timeout_sec=cfg.FALL_TIMEOUT_SEC,
                stale_after_sec=cfg.FALL_STALE_AFTER_SEC,
            )
            fall_client.start()
            print(f"[app] Fall detection ON. Server: {args.fall_server}")
        except Exception as exc:
            print(f"[app] WARNING: fall detection disabled ({exc})")
            fall_client = None

    print("[app] White-line follower started.")
    print("[app] Stop with Ctrl+C.")

    if args.debug:
        print("[app] Debug mode enabled. Press q to quit.")

    frame_idx = 0
    has_display = args.debug and _display_available()
    render_debug = has_display or stream_server is not None

    if has_display:
        for name in ("vision-test", "white-line-mask"):
            cv2.namedWindow(name, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(name, cfg.DEBUG_WINDOW_WIDTH, cfg.DEBUG_WINDOW_HEIGHT)

    try:
        while True:
            frame = camera.read()

            # Highest-priority override: stop the car while a human appears
            # to be falling/fallen. Still push the USB-camera stream so the
            # operator can see what the server is seeing.
            if fall_client is not None:
                fall_state = fall_client.state()
                if stream_server is not None and fall_state.annotated_frame is not None:
                    stream_server.push("fall", fall_state.annotated_frame)
                if fall_state.falling:
                    if args.debug and frame_idx % 15 == 0:
                        print(
                            f"[fall] STOPPED falling=True "
                            f"infer={fall_state.infer_ms:.0f}ms "
                            f"people={len(fall_state.people)}"
                        )
                    motor.stop()
                    frame_idx += 1
                    time.sleep(cfg.CONTROL_DELAY_SEC)
                    continue

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

            lost_info = ""
            if action == "lost":
                # Reset PID so stale state doesn't cause a jerk on reacquire.
                steering_pid.reset()
                if cfg.STOP_WHEN_LINE_LOST:
                    motor.stop()
                else:
                    lost_info = handle_lost_line(motor, searcher, avoider)
            else:
                searcher.reset()
                left_speed, right_speed = steering_speeds(detection.offset_x)
                motor.differential(left_speed, right_speed)

            if args.debug and frame_idx % 15 == 0:
                tail = f" {lost_info}" if lost_info else ""
                print(
                    f"[app] frame={frame_idx} found={detection.found} "
                    f"offset={detection.offset_x} area={int(detection.area)} "
                    f"action={action}{tail}"
                )

            if render_debug:
                debug = draw_debug(frame, detection)

                if stream_server is not None:
                    stream_server.push("main", debug)
                    stream_server.push("mask", detection.mask)

                if has_display:
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
        if fall_client is not None:
            fall_client.stop()
        if stream_server is not None:
            stream_server.stop()
        if avoider is not None:
            avoider.cleanup()
        motor.safe_stop()
        camera.release()
        cv2.destroyAllWindows()
        _gpio_cleanup()
        print("[app] Done.")


if __name__ == "__main__":
    main()
