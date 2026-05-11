from __future__ import annotations

import cv2

from raspbot.config import AppConfig
from raspbot.hardware import PiCamera
from raspbot.vision import GreenLaneDetector


def main() -> None:
    config = AppConfig()
    camera = PiCamera(config.camera)
    detector = GreenLaneDetector(config.lane)

    print("Camera + lane detector test. Press 'q' to stop.")

    camera.start()

    try:
        while True:
            frame = camera.read_bgr()
            _, debug_frame = detector.detect(frame)

            cv2.imshow("Camera Lane Test", debug_frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    finally:
        camera.stop()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
