"""
Standalone test of the fall-detection pipeline. NO motors, NO line follower.

Reads from the USB camera, POSTs frames to the laptop server, prints results
every second, and optionally serves an MJPEG dashboard so you can watch the
bounding boxes from your laptop browser.

Examples:

Console only (server reachable on the IP in config.py):
    python -m scripts.fall_test

Override server URL:
    python -m scripts.fall_test --fall-server http://192.168.1.55:8000

Show the annotated stream in your browser:
    python -m scripts.fall_test --stream
    # then open http://<pi-ip>:8080/fall.mjpg on your laptop

Use a different USB camera:
    python -m scripts.fall_test --fall-camera-index 2
"""

from __future__ import annotations

import argparse
import time

import raspbot.config as cfg
from raspbot.vision.fall_detector import FallDetectorClient
from raspbot.vision.mjpeg_server import MJPEGServer


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fall-server", default=cfg.FALL_SERVER_URL)
    parser.add_argument(
        "--fall-camera-index", type=int, default=cfg.FALL_USB_CAMERA_INDEX
    )
    parser.add_argument("--fall-fps", type=float, default=cfg.FALL_TARGET_FPS)
    parser.add_argument(
        "--stream",
        action="store_true",
        help="Serve the annotated USB-camera feed at http://<pi-ip>:<port>/fall.mjpg",
    )
    parser.add_argument("--stream-port", type=int, default=8080)
    parser.add_argument("--stream-fps", type=int, default=15)
    parser.add_argument(
        "--print-interval", type=float, default=1.0,
        help="How often to print state to console (seconds).",
    )
    args = parser.parse_args()

    print(f"[test] server : {args.fall_server}")
    print(f"[test] camera : index {args.fall_camera_index}")
    print(f"[test] fps    : {args.fall_fps}")

    stream_server: MJPEGServer | None = None
    if args.stream:
        stream_server = MJPEGServer(
            port=args.stream_port, fps_cap=args.stream_fps
        )
        stream_server.start()
        print(
            f"[test] MJPEG live: http://<pi-ip>:{args.stream_port}/fall.mjpg "
            f"(or open / for the full dashboard)"
        )

    try:
        client = FallDetectorClient(
            server_url=args.fall_server,
            camera_index=args.fall_camera_index,
            camera_width=cfg.FALL_CAMERA_WIDTH,
            camera_height=cfg.FALL_CAMERA_HEIGHT,
            target_fps=args.fall_fps,
            jpeg_quality=cfg.FALL_JPEG_QUALITY,
            timeout_sec=cfg.FALL_TIMEOUT_SEC,
            stale_after_sec=cfg.FALL_STALE_AFTER_SEC,
        )
        client.start()
    except Exception as exc:
        print(f"[test] FAILED to start: {exc}")
        if stream_server is not None:
            stream_server.stop()
        return

    print("[test] running — Ctrl+C to stop.")

    last_print = 0.0
    try:
        while True:
            state = client.state()

            if stream_server is not None and state.annotated_frame is not None:
                stream_server.push("fall", state.annotated_frame)

            now = time.time()
            if now - last_print >= args.print_interval:
                last_print = now
                flag = "FALL  " if state.falling else "ok    "
                age = (now - state.last_update) if state.last_update else None
                age_str = f"{age:.1f}s ago" if age is not None else "no update yet"
                err = f"  error={state.last_error}" if state.last_error else ""
                print(
                    f"[{flag}]  people={len(state.people)}  "
                    f"infer={state.infer_ms:.0f}ms  last={age_str}{err}"
                )

            time.sleep(0.05)
    except KeyboardInterrupt:
        print("\n[test] stopping.")
    finally:
        client.stop()
        if stream_server is not None:
            stream_server.stop()
        print("[test] done.")


if __name__ == "__main__":
    main()
