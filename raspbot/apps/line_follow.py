"""
Main app: white-line follower with fall detection + voice handoff.

Behavior priority each frame (highest first):
    1. Voice session active        → STAY parked.
    2. Fall detected               → STOP immediately, trigger voice session.
    3. Obstacle within OBSTACLE_DISTANCE_CM → STOP, then rotate right by
                                    OBSTACLE_TURN_DEGREES (default 60°).
                                    Repeats while the obstacle stays in range.
    4. White line visible          → PID differential drive.
    5. White line lost             → sweep search (alternating left/right).

Examples:

    # Pi camera, real run:
    python -m raspbot.apps.line_follow --camera picamera2

    # Safe dry-run (prints motor commands, wheels don't move):
    python -m raspbot.apps.line_follow --camera picamera2 --dry-run --debug

    # Full production setup — stream + fall detection + voice:
    python -m raspbot.apps.line_follow --camera picamera2 \\
        --stream --fall-detection --voice --debug
"""

from __future__ import annotations

import argparse
import os
import time
from enum import Enum

import cv2

import raspbot.config as cfg
from raspbot.hardware.avoider import Sensors
from raspbot.hardware.motor import MotorController
from raspbot.hardware.pid import PIDController
from raspbot.vision.camera import create_camera
from raspbot.vision.fall_detector import FallDetectorClient
from raspbot.vision.mjpeg_server import MJPEGServer
from raspbot.vision.white_line_detector import WhiteLineDetector, draw_debug
from raspbot.voice.voice_agent_client import VoiceAgentClient


# ─── steering ────────────────────────────────────────────────────────────────

steering_pid = PIDController(
    kp=cfg.STEERING_PID_KP,
    ki=cfg.STEERING_PID_KI,
    kd=cfg.STEERING_PID_KD,
    output_limit=cfg.STEERING_PID_OUTPUT_LIMIT,
    integral_limit=cfg.STEERING_PID_INTEGRAL_LIMIT,
)


def steering_speeds(offset_x: int) -> tuple[int, int]:
    """PID-driven differential drive. Returns (left_speed, right_speed)."""
    base = cfg.FORWARD_SPEED
    deadband = cfg.CENTER_TOLERANCE_PX

    # Inside the deadband, drive straight but still feed 0 into the PID so the
    # derivative term doesn't see a discontinuity at the deadband boundary.
    error = 0.0 if abs(offset_x) <= deadband else float(offset_x)
    correction = int(steering_pid.update(error))

    if correction >= 0:
        # offset positive → line is right of center → slow RIGHT wheel.
        return (base, max(0, base - correction))

    # offset negative → line is left of center → slow LEFT wheel.
    return (max(0, base + correction), base)


# ─── line searcher ───────────────────────────────────────────────────────────

class LineSearcher:
    """Brief stop, then alternating left/right sweep until the line is found."""

    def __init__(self) -> None:
        self._direction = "right"
        self._sweep_started: float | None = None
        self._entered_at: float | None = None

    def reset(self) -> None:
        self._direction = "right"
        self._sweep_started = None
        self._entered_at = None

    def step(self, motor: MotorController) -> str:
        now = time.monotonic()

        if self._entered_at is None:
            self._entered_at = now

        # Phase 1: brief stop on entry so the search visibly pauses.
        if now - self._entered_at < cfg.SEARCH_INITIAL_STOP_SEC:
            motor.stop()
            return "stop"

        # Phase 2: alternating sweep.
        if self._sweep_started is None:
            self._sweep_started = now
        elif now - self._sweep_started >= cfg.SEARCH_SWEEP_SEC:
            self._direction = "left" if self._direction == "right" else "right"
            self._sweep_started = now

        if self._direction == "right":
            motor.spin_right(cfg.SEARCH_TURN_SPEED)
        else:
            motor.spin_left(cfg.SEARCH_TURN_SPEED)

        return f"sweep-{self._direction}"


# ─── obstacle avoider ────────────────────────────────────────────────────────

class ObstacleAvoider:
    """Brief stop, then a fixed right-turn of cfg.OBSTACLE_TURN_DEGREES.

    The maneuver auto-resets when complete, so if the obstacle is still in
    range on the next frame the bot does another OBSTACLE_TURN_DEGREES turn
    (60° → 120° → 180° → …) until the path clears.
    """

    def __init__(self) -> None:
        self._phase: str = "stop"  # "stop" → "turn" → "done"
        self._phase_started_at: float | None = None

    def reset(self) -> None:
        self._phase = "stop"
        self._phase_started_at = None

    def step(self, motor: MotorController) -> str:
        now = time.monotonic()

        if self._phase_started_at is None:
            self._phase_started_at = now

        elapsed = now - self._phase_started_at

        if self._phase == "stop":
            if elapsed < cfg.SEARCH_INITIAL_STOP_SEC:
                motor.stop()
                return "obstacle-stop"
            self._phase = "turn"
            self._phase_started_at = now
            elapsed = 0.0

        if self._phase == "turn":
            turn_dur = cfg.OBSTACLE_TURN_DEGREES * cfg.OBSTACLE_TURN_SEC_PER_DEGREE
            if elapsed < turn_dur:
                motor.spin_right(cfg.OBSTACLE_TURN_SPEED)
                return "obstacle-turn-right"
            # Turn complete — reset so the next frame starts a fresh 60°
            # turn if the obstacle is still detected.
            motor.stop()
            self.reset()
            return "obstacle-turn-done"

        motor.stop()
        return "obstacle-idle"


# ─── state machine ───────────────────────────────────────────────────────────

class State(Enum):
    FOLLOW = "follow"
    SEARCH = "search"
    OBSTACLE = "obstacle"
    FALL = "fall"
    VOICE = "voice"


# ─── helpers ─────────────────────────────────────────────────────────────────

def _display_available() -> bool:
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def _gpio_cleanup() -> None:
    try:
        import RPi.GPIO as GPIO  # type: ignore
        GPIO.cleanup()
    except Exception:
        pass


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--camera", choices=["picamera2", "usb"], default="picamera2")
    parser.add_argument("--camera-index", type=int, default=cfg.USB_CAMERA_INDEX)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--no-sensors",
        action="store_true",
        help="Disable ultrasonic + IR sensor init (use when sensors not wired).",
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
    parser.add_argument(
        "--voice",
        action="store_true",
        help="Trigger Night Officer voice agent when stopped at a fallen person.",
    )
    parser.add_argument("--voice-api", default=cfg.VOICE_API_URL)
    parser.add_argument("--voice-robot-id", default=cfg.VOICE_ROBOT_ID)
    return parser.parse_args()


# ─── main loop ───────────────────────────────────────────────────────────────

def main() -> None:
    args = _parse_args()

    camera = create_camera(
        camera_type=args.camera,
        index=args.camera_index,
        width=cfg.CAMERA_WIDTH,
        height=cfg.CAMERA_HEIGHT,
        fps=cfg.CAMERA_FPS,
    )

    motor = MotorController(dry_run=args.dry_run)
    detector = WhiteLineDetector()
    searcher = LineSearcher()
    avoider = ObstacleAvoider()

    sensors: Sensors | None = None
    if cfg.SENSORS_ENABLED and not args.no_sensors:
        try:
            sensors = Sensors(simulate=args.dry_run)
            print("[app] Sensors enabled.")
        except Exception as exc:
            print(f"[app] WARNING: sensors disabled ({exc})")
            sensors = None
    else:
        print("[app] Sensors OFF.")

    stream_server: MJPEGServer | None = None
    if args.stream:
        stream_server = MJPEGServer(port=args.stream_port, fps_cap=args.stream_fps)
        stream_server.start()
        print(
            f"[app] MJPEG stream live: open http://<pi-ip>:{args.stream_port}/ "
            "in a browser on your laptop."
        )

    voice: VoiceAgentClient | None = None
    if args.voice:
        voice = VoiceAgentClient(
            api_url=args.voice_api,
            robot_id=args.voice_robot_id,
            timeout_sec=cfg.VOICE_API_TIMEOUT_SEC,
            trigger_stop_seconds=cfg.VOICE_TRIGGER_STOP_SECONDS,
            end_after_no_fall_seconds=cfg.VOICE_END_AFTER_NO_FALL_SECONDS,
            retry_cooldown_seconds=cfg.VOICE_RETRY_COOLDOWN_SEC,
        )
        print(f"[app] Voice agent ON. API: {args.voice_api}")

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

    print("[app] White-line follower started. Stop with Ctrl+C.")
    if args.debug:
        print("[app] Debug mode enabled. Press q in the OpenCV window to quit.")

    has_display = args.debug and _display_available()
    render_debug = has_display or stream_server is not None

    if has_display:
        for name in ("vision-test", "white-line-mask"):
            cv2.namedWindow(name, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(name, cfg.DEBUG_WINDOW_WIDTH, cfg.DEBUG_WINDOW_HEIGHT)

    frame_idx = 0
    prev_state: State | None = None

    try:
        while True:
            # ── 1. SENSE ────────────────────────────────────────────────────
            frame = camera.read()
            detection = detector.detect(frame)

            fall_state = fall_client.state() if fall_client is not None else None
            falling = bool(fall_state and fall_state.falling)

            distance_cm = sensors.distance_cm() if sensors is not None else float("inf")
            obstacle_ahead = (
                sensors is not None and distance_cm <= cfg.OBSTACLE_DISTANCE_CM
            )

            # Push fall annotated frame to MJPEG stream regardless of state.
            if (
                stream_server is not None
                and fall_state is not None
                and fall_state.annotated_frame is not None
            ):
                stream_server.push("fall", fall_state.annotated_frame)

            # Drive the voice client's debounce. We stop immediately on fall,
            # so `arrived` always matches `falling`.
            if voice is not None:
                voice.tick(falling=falling, arrived=falling)

            # ── 2. DECIDE ───────────────────────────────────────────────────
            if voice is not None and voice.is_active():
                state = State.VOICE
            elif falling:
                state = State.FALL
            elif obstacle_ahead:
                state = State.OBSTACLE
            elif detection.found:
                state = State.FOLLOW
            else:
                state = State.SEARCH

            # ── 3. ACT ──────────────────────────────────────────────────────
            if state in (State.VOICE, State.FALL):
                motor.stop()
                steering_pid.reset()
                searcher.reset()
                avoider.reset()

            elif state == State.OBSTACLE:
                steering_pid.reset()
                searcher.reset()
                avoider.step(motor)  # brief stop, then 60° right turn

            elif state == State.FOLLOW:
                searcher.reset()
                avoider.reset()
                left_speed, right_speed = steering_speeds(detection.offset_x)
                motor.differential(left_speed, right_speed)

            elif state == State.SEARCH:
                steering_pid.reset()
                avoider.reset()
                searcher.step(motor)

            # ── 4. LOG / RENDER ─────────────────────────────────────────────
            if args.debug and (state != prev_state or frame_idx % 30 == 0):
                _log_state(state, detection, distance_cm, voice, fall_state, frame_idx)

            if render_debug:
                debug = draw_debug(frame, detection)
                if stream_server is not None:
                    stream_server.push("main", debug)
                    stream_server.push("mask", detection.mask)
                if has_display:
                    cv2.imshow("vision-test", debug)
                    cv2.imshow("white-line-mask", detection.mask)
                    if (cv2.waitKey(1) & 0xFF) == ord("q"):
                        break

            prev_state = state
            frame_idx += 1
            time.sleep(cfg.CONTROL_DELAY_SEC)

    except KeyboardInterrupt:
        print("\n[app] Ctrl+C received. Stopping.")
    finally:
        if voice is not None:
            voice.shutdown()
        if fall_client is not None:
            fall_client.stop()
        if stream_server is not None:
            stream_server.stop()
        if sensors is not None:
            sensors.cleanup()
        motor.safe_stop()
        camera.release()
        cv2.destroyAllWindows()
        _gpio_cleanup()
        print("[app] Done.")


def _log_state(
    state: State,
    detection,
    distance_cm: float,
    voice: VoiceAgentClient | None,
    fall_state,
    frame_idx: int,
) -> None:
    dist = "inf" if distance_cm == float("inf") else f"{distance_cm:.1f}cm"
    line = (
        f"found offset={detection.offset_x}" if detection.found else "lost"
    )
    extras = []
    if fall_state is not None:
        extras.append(f"falling={fall_state.falling}")
    if voice is not None and voice.is_active():
        extras.append(f"room={voice.current_room()}")
    extras_str = "  " + "  ".join(extras) if extras else ""
    print(
        f"[app] frame={frame_idx} state={state.value:<8} "
        f"line={line}  dist={dist}{extras_str}"
    )


if __name__ == "__main__":
    main()
