"""
Camera test.

Pi camera:
    python -m scripts.camera_test --camera picamera2

USB camera:
    python -m scripts.camera_test --camera usb --camera-index 0

Press q to quit.
"""

import argparse

import cv2

import raspbot.config as cfg
from raspbot.vision.camera import create_camera


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--camera", choices=["picamera2", "usb"], default="picamera2")
    parser.add_argument("--camera-index", type=int, default=cfg.USB_CAMERA_INDEX)
    args = parser.parse_args()

    camera = create_camera(
        camera_type=args.camera,
        index=args.camera_index,
        width=cfg.CAMERA_WIDTH,
        height=cfg.CAMERA_HEIGHT,
        fps=cfg.CAMERA_FPS,
    )

    print("Camera test started. Press q to quit.")

    try:
        while True:
            frame = camera.read()
            cv2.imshow("camera-test", frame)

            key = cv2.waitKey(1) & 0xFF

            if key == ord("q"):
                break
    finally:
        camera.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
