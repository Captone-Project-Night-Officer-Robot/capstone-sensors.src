"""
White-line vision test. Motors do not move.

Pi camera:
    python -m scripts.vision_test --camera picamera2

USB camera:
    python -m scripts.vision_test --camera usb --camera-index 0

Press q to quit.
"""

import argparse

import cv2

import raspbot.config as cfg
from raspbot.vision.camera import create_camera
from raspbot.vision.white_line_detector import WhiteLineDetector, draw_debug


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

    detector = WhiteLineDetector()

    print("Vision test started. Press q to quit.")
    print("In white-line-mask window, the line should be white and background black.")

    try:
        while True:
            frame = camera.read()
            detection = detector.detect(frame)
            debug = draw_debug(frame, detection)

            cv2.imshow("vision-test", debug)
            cv2.imshow("white-line-mask", detection.mask)

            key = cv2.waitKey(1) & 0xFF

            if key == ord("q"):
                break
    finally:
        camera.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
