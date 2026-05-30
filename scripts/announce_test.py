"""
Standalone patrol-announcement test. No camera, no YOLO, no motors.

Fetches the bilingual safety announcement from the voice server
(capstone.voice-src → /api/v1/announce/patrol.wav) and loops it through the
Pi speaker — the exact audio path the robot uses while driving, but with
nothing else running. Use it to verify the speaker + the speech end-to-end.

Prerequisites:
    • Laptop running the voice server:
        cd capstone.voice-src && uvicorn src.main:app --host 0.0.0.0 --port 8001
    • Pi speaker working: libportaudio2 + sounddevice (see install_pi.sh).

Usage:

    # Loop the announcement for 30s against the URL in raspbot/config.py:
    python -m scripts.announce_test

    # Point at a specific voice server:
    python -m scripts.announce_test --api-url http://192.168.1.55:8001

    # Loop until Ctrl+C:
    python -m scripts.announce_test --duration 0

    # Shorter gap between repeats:
    python -m scripts.announce_test --gap 2
"""

from __future__ import annotations

import argparse
import time

import raspbot.config as cfg
from raspbot.voice.patrol_announcer import (
    PatrolAnnouncer,
    _HAS_NUMPY,
    _HAS_SOUNDDEVICE,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Standalone patrol-announcement test (no robot)."
    )
    parser.add_argument(
        "--api-url",
        default=cfg.PATROL_ANNOUNCE_API_URL,
        help=f"Voice server URL (default: {cfg.PATROL_ANNOUNCE_API_URL})",
    )
    parser.add_argument(
        "--gap",
        type=float,
        default=cfg.PATROL_ANNOUNCE_GAP_SEC,
        help=f"Silence between repeats, seconds (default: {cfg.PATROL_ANNOUNCE_GAP_SEC})",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=30.0,
        help="Seconds to keep announcing. 0 = until Ctrl+C. (default: 30)",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    print("=" * 64)
    print("[announce-test] standalone patrol-announcement test")
    print("=" * 64)
    print(f"  voice server        : {args.api_url}")
    print(f"  gap between repeats : {args.gap:.1f}s")
    dur = f"{args.duration:.1f}s" if args.duration > 0 else "until Ctrl+C"
    print(f"  duration            : {dur}")
    print(f"  speaker device      : {cfg.PATROL_ANNOUNCE_SPEAKER_DEVICE or '<default>'}")
    print(f"  sounddevice present : {_HAS_SOUNDDEVICE}")
    print(f"  numpy present       : {_HAS_NUMPY}")
    print("-" * 64)

    announcer = PatrolAnnouncer(
        api_url=args.api_url,
        gap_sec=args.gap,
        speaker_device=cfg.PATROL_ANNOUNCE_SPEAKER_DEVICE,
        fetch_timeout_sec=cfg.PATROL_ANNOUNCE_FETCH_TIMEOUT_SEC,
    )

    try:
        announcer.start()
    except Exception as exc:
        print(f"[announce-test] FAILED to start: {exc}")
        return

    print("[announce-test] announcing — you should hear EN + KR on a loop.")
    print("               Ctrl+C to stop.")

    announcer.set_active(True)
    try:
        start = time.time()
        while True:
            if args.duration > 0 and (time.time() - start) >= args.duration:
                break
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("\n[announce-test] Ctrl+C received.")
    finally:
        announcer.set_active(False)
        announcer.stop()
        print("[announce-test] done.")


if __name__ == "__main__":
    main()
