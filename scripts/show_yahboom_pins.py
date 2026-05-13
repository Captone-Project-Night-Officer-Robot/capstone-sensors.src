"""
Show motor pin constants from official Yahboom CarRun.py.

Example:
    python -m scripts.show_yahboom_pins --repo ~/workspace/RaspberryPi-4WD-Car
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


PIN_NAMES = ["IN1", "IN2", "IN3", "IN4", "ENA", "ENB"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=str(Path.home() / "workspace" / "RaspberryPi-4WD-Car"))
    args = parser.parse_args()

    repo = Path(args.repo).expanduser()
    car_run = repo / "4.Code" / "python" / "CarRun.py"

    if not car_run.exists():
        raise SystemExit(f"Could not find official CarRun.py at: {car_run}")

    text = car_run.read_text(encoding="utf-8", errors="ignore")

    print(f"Reading: {car_run}")
    print("Detected pin constants:")

    found_any = False

    for name in PIN_NAMES:
        match = re.search(rf"^\s*{name}\s*=\s*(\d+)\s*$", text, re.MULTILINE)
        if match:
            found_any = True
            print(f"{name} = {match.group(1)}")
        else:
            print(f"{name} = NOT FOUND")

    if not found_any:
        print("\nNo pin constants found. Open CarRun.py manually and check the top section.")


if __name__ == "__main__":
    main()
