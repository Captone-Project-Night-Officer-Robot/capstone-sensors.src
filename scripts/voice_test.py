"""
Standalone voice-session test for the Pi. No camera, no YOLO, no motors.

Triggers a LiveKit voice session by hand and holds it for a configurable
duration. While the session is active:

    • The Pi mic publishes into the room (the agent's STT hears you).
    • The Pi speaker plays the agent's TTS.

Use this to verify Pi audio I/O end-to-end without rigging up a fake fall
in front of the YOLO camera.

Prerequisites (one-time, on the Pi):

    sudo apt install libportaudio2
    source .venv/bin/activate
    pip install livekit sounddevice

The laptop must be running:
    1. capstone.voice-src   →  uvicorn src.main:app --port 8001
    2. capstone.voice-src   →  python -m src.worker dev

Usage:

    # 30-second session against the URL in raspbot/config.py:
    python -m scripts.voice_test

    # Override the voice API and robot id:
    python -m scripts.voice_test --api-url http://192.168.1.55:8001 --robot-id rig-1

    # Speaker-only — don't publish mic (one-way TTS test):
    python -m scripts.voice_test --no-mic

    # Hold session until Ctrl+C:
    python -m scripts.voice_test --duration 0
"""

from __future__ import annotations

import argparse
import time

import raspbot.config as cfg
from raspbot.voice.voice_agent_client import (
    VoiceAgentClient,
    _HAS_LIVEKIT,
    _HAS_SOUNDDEVICE,
)


TICK_PERIOD_SEC = 0.1


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Standalone Pi voice-session test (no robot)."
    )
    parser.add_argument(
        "--api-url",
        default=cfg.VOICE_API_URL,
        help=f"FastAPI voice server URL (default: {cfg.VOICE_API_URL})",
    )
    parser.add_argument(
        "--robot-id",
        default=cfg.VOICE_ROBOT_ID,
        help=f"Identity sent to the voice API (default: {cfg.VOICE_ROBOT_ID})",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=30.0,
        help="Seconds to hold the session. Pass 0 to hold until Ctrl+C. "
        "(default: 30)",
    )
    parser.add_argument(
        "--no-mic",
        action="store_true",
        help="Don't publish the Pi mic — speaker-only TTS smoke test.",
    )
    parser.add_argument(
        "--trigger-debounce",
        type=float,
        default=0.0,
        help="Override VOICE_TRIGGER_STOP_SECONDS for this test (default: 0 "
        "= start instantly).",
    )
    parser.add_argument(
        "--end-debounce",
        type=float,
        default=2.0,
        help="Override VOICE_END_AFTER_NO_FALL_SECONDS for this test "
        "(default: 2s — short so the script exits quickly).",
    )
    return parser.parse_args()


def _preflight(args: argparse.Namespace) -> None:
    print("=" * 64)
    print("[voice-test] Pi voice-session standalone test")
    print("=" * 64)
    print(f"  voice API           : {args.api_url}")
    print(f"  robot_id            : {args.robot_id}")
    duration = f"{args.duration:.1f}s" if args.duration > 0 else "until Ctrl+C"
    print(f"  hold duration       : {duration}")
    print(f"  mic publish         : {'OFF (--no-mic)' if args.no_mic else 'ON'}")
    print(f"  livekit installed   : {_HAS_LIVEKIT}")
    print(f"  sounddevice present : {_HAS_SOUNDDEVICE}")
    print(f"  mic device          : {cfg.VOICE_MIC_DEVICE or '<default>'}")
    print(f"  speaker device      : {cfg.VOICE_SPEAKER_DEVICE or '<default>'}")
    print(f"  mic sample rate     : {cfg.VOICE_MIC_SAMPLE_RATE} Hz")
    print("-" * 64)

    if not _HAS_LIVEKIT:
        print(
            "[voice-test] WARNING: livekit SDK missing — the Pi will log a "
            "session but not actually join the room. Install: pip install livekit"
        )
    if not _HAS_SOUNDDEVICE:
        print(
            "[voice-test] WARNING: sounddevice missing — no Pi mic/speaker. "
            "Install: sudo apt install libportaudio2 && pip install sounddevice"
        )


def main() -> None:
    args = _parse_args()
    _preflight(args)

    # Temporarily override mic-enable for this test if --no-mic was passed.
    original_mic_enabled = cfg.VOICE_MIC_ENABLED
    if args.no_mic:
        cfg.VOICE_MIC_ENABLED = False

    client = VoiceAgentClient(
        api_url=args.api_url,
        robot_id=args.robot_id,
        timeout_sec=cfg.VOICE_API_TIMEOUT_SEC,
        trigger_stop_seconds=args.trigger_debounce,
        end_after_no_fall_seconds=args.end_debounce,
        retry_cooldown_seconds=cfg.VOICE_RETRY_COOLDOWN_SEC,
    )

    print("[voice-test] triggering session (falling=True)...")
    interrupted = False

    try:
        # Phase 1: drive falling=True until the session is active.
        deadline = time.time() + 10.0
        while not client.is_active():
            client.tick(falling=True, arrived=True)
            if time.time() > deadline:
                print(
                    "[voice-test] FAILED: session did not become active "
                    "within 10s. Is the voice API reachable? Worker running?"
                )
                return
            time.sleep(TICK_PERIOD_SEC)

        print(f"[voice-test] session active. room={client.current_room()}")
        print(
            "[voice-test] Speak into the mic — the agent should reply through "
            "the speaker.\n"
            "             Ctrl+C to end early."
        )

        # Phase 2: hold the session, keep ticking falling=True so it stays up.
        start = time.time()
        while True:
            client.tick(falling=True, arrived=True)
            if args.duration > 0 and (time.time() - start) >= args.duration:
                break
            time.sleep(TICK_PERIOD_SEC)

        print(f"[voice-test] duration reached ({args.duration:.1f}s). "
              "winding down...")

    except KeyboardInterrupt:
        interrupted = True
        print("\n[voice-test] Ctrl+C received. winding down...")

    finally:
        # Phase 3: tick falling=False until the client ends the session.
        deadline = time.time() + max(args.end_debounce, 1.0) + 5.0
        while client.is_active() and time.time() < deadline:
            client.tick(falling=False, arrived=False)
            time.sleep(TICK_PERIOD_SEC)

        client.shutdown()

        # Restore config (in case the test is run from a long-lived REPL).
        cfg.VOICE_MIC_ENABLED = original_mic_enabled

        print(f"[voice-test] done."
              f"{' (interrupted)' if interrupted else ''}")


if __name__ == "__main__":
    main()
