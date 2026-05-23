"""
Configuration for the Yahboom Pi4WD line-follower robot.

Behavior priority (highest first):
  1. Voice session active        → STAY parked (don't drive mid-conversation)
  2. Fall detected               → STOP immediately, trigger voice session
  3. Obstacle within OBSTACLE_DISTANCE_CM → STOP, then sweep to search the line
  4. White line visible          → PID differential drive along the line
  5. White line lost             → sweep search (alternating left/right)
"""

# -----------------------------
# Camera settings
# -----------------------------

CAMERA_WIDTH = 320
CAMERA_HEIGHT = 240
CAMERA_FPS = 30
USB_CAMERA_INDEX = 0

# Size of the debug visualisation windows (pixels). The camera frame is
# upscaled to this size for display only — control logic still runs on the
# original CAMERA_WIDTH x CAMERA_HEIGHT frame.
DEBUG_WINDOW_WIDTH = 800
DEBUG_WINDOW_HEIGHT = 600

# Use only lower part of image.
# 0.55 means ignore top 55%, use bottom 45%.
ROI_TOP_RATIO = 0.55


# -----------------------------
# White line detection
# -----------------------------
# White in HSV = high V (brightness), low S (saturation).
# Lower WHITE_VALUE_MIN if the line isn't detected.
# Raise it if background is detected as white.
WHITE_VALUE_MIN = 180

# Lower if bright colored objects are detected as the line.
WHITE_SATURATION_MAX = 80

# Ignore small noise contours.
MIN_CONTOUR_AREA = 350

# If the line center is within this many pixels of frame center, drive straight.
CENTER_TOLERANCE_PX = 25

# Morphological open/close on the mask.
USE_MORPHOLOGY = True


# -----------------------------
# Motor behavior
# -----------------------------

FORWARD_SPEED = 30
TURN_SPEED = 45
SEARCH_TURN_SPEED = 22

# PID gains for line steering. Converts pixel offset (line_x - frame_cx)
# into a differential wheel-speed correction.
#
# Tuning order:
#   1. Set KI=KD=0. Raise KP until the car holds the line but slightly wobbles.
#   2. Add KD to damp the wobble (start small).
#   3. Add KI only if there's persistent off-center drift on straight lines.
#
# Output is clamped to ±STEERING_PID_OUTPUT_LIMIT (wheel-speed units, 0-100).
STEERING_PID_KP = 0.30
STEERING_PID_KI = 0.0
STEERING_PID_KD = 0.05
STEERING_PID_OUTPUT_LIMIT = 35
STEERING_PID_INTEGRAL_LIMIT = 200

CONTROL_DELAY_SEC = 0.03

# How long each sweep direction runs before reversing (seconds).
SEARCH_SWEEP_SEC = 0.4

# Brief stop before sweep starts, so the search visibly pauses on obstacle
# / line-lost transitions.
SEARCH_INITIAL_STOP_SEC = 0.3

# Flip these if motors run the wrong direction.
INVERT_FORWARD = False
INVERT_STEERING = False


# -----------------------------
# Yahboom Pi4WD GPIO pins (from official 4.Code/python/CarRun.py)
# -----------------------------

IN1 = 20
IN2 = 21
IN3 = 19
IN4 = 26
ENA = 16
ENB = 13

PWM_FREQUENCY = 2000


# -----------------------------
# Ultrasonic obstacle sensor (HC-SR04)
# BCM numbering. BCM 23 = BOARD 16, BCM 24 = BOARD 18.
# -----------------------------

ULTRASONIC_TRIG = 23
ULTRASONIC_ECHO = 24

# Background polling rate of the ultrasonic thread.
ULTRASONIC_POLL_HZ = 20

# Echo timeout. Longer = more tolerant of slow returns, but slower poll loop.
ULTRASONIC_TIMEOUT_SEC = 0.03

# Discard readings outside this band — sensor is unreliable there.
ULTRASONIC_MIN_CM = 3.0
ULTRASONIC_MAX_CM = 200.0


# -----------------------------
# IR obstacle sensors (digital, active-low: LOW = obstacle present)
# BCM numbering. BCM 9 = BOARD 21, BCM 10 = BOARD 19, BCM 25 = BOARD 22.
# -----------------------------

# Set False if IR is not wired or you want pure-camera sweep search.
IR_ENABLED = False

IR_LEFT_PIN = 9
IR_RIGHT_PIN = 10

# Some Yahboom boards expose an "IR enable" pin that must be driven HIGH.
# Set to None if your board does not have one.
IR_POWER_PIN = 25

# Yahboom's stock IR sensors are active-LOW. Flip this if your 3rd-party
# modules report "blocked" when nothing is in front of them.
IR_ACTIVE_LOW = True


# -----------------------------
# Obstacle behavior
# -----------------------------

# Master switch for sensor init. Set False to skip ultrasonic/IR entirely
# (e.g. when those sensors are not wired yet).
SENSORS_ENABLED = True

# When the front ultrasonic reports anything closer than this, the robot
# STOPS and starts a sweep search for the white line (i.e. it tries to find
# the line in a new heading that bypasses the obstacle).
OBSTACLE_DISTANCE_CM = 20.0


# -----------------------------
# Fall detection (remote inference)
# A USB camera on the car is read in a background thread and frames are
# POSTed to the FastAPI server in capstone-falldetection.src (running on the
# laptop). When `falling=True`, the car STOPS IMMEDIATELY and triggers the
# voice agent.
# -----------------------------

# Replace with your laptop's IP — the one that runs server.py.
FALL_SERVER_URL = "http://172.20.10.12:8000"

# Which USB camera (cv2.VideoCapture index) to read from.
FALL_USB_CAMERA_INDEX = 0
FALL_CAMERA_WIDTH = 640
FALL_CAMERA_HEIGHT = 480

# Frames per second sent to the server. Fall events are slow — 5 fps is
# plenty and keeps wifi/CPU load low.
FALL_TARGET_FPS = 5

# JPEG quality of uploaded frames. 70 is a good size/quality balance.
FALL_JPEG_QUALITY = 70

# Per-request HTTP timeout (sec). Increase if your laptop is slow.
FALL_TIMEOUT_SEC = 2.0

# If the server stops responding for this many seconds, the cached "falling"
# state is forced back to False so the car doesn't sit forever.
FALL_STALE_AFTER_SEC = 3.0


# -----------------------------
# Voice-agent integration (capstone.voice-src)
# -----------------------------

# Base URL of the FastAPI voice server (capstone.voice-src/src/main.py).
VOICE_API_URL = "http://172.20.10.12:8001"

# Identifier reported to the voice API as `robot_id`.
VOICE_ROBOT_ID = "raspbot-01"

# Debounce: only start a voice session after the car has been stopped on a
# detected fall for this many seconds. Keeps brief YOLO flickers from
# triggering the agent.
VOICE_TRIGGER_STOP_SECONDS = 1.0

# End the voice session when `falling` has been False this long.
# 15s is the production default — long enough that YOLO flickers don't
# drop the session, short enough that the agent doesn't talk to thin air.
VOICE_END_AFTER_NO_FALL_SECONDS = 15.0

# HTTP timeout for the session-start call.
VOICE_API_TIMEOUT_SEC = 5.0

# After a failed session-start (server down, wrong URL, etc.) wait this long
# before retrying. Prevents the log from filling up.
VOICE_RETRY_COOLDOWN_SEC = 5.0


# -----------------------------
# Voice-agent audio I/O (Pi mic + speaker)
# Phase 2: the Pi joins the LiveKit room with a real mic track and plays
# the agent's TTS through a real speaker. Requires sounddevice + portaudio.
# -----------------------------

# Capture mic audio and publish it to the room so the agent can hear the
# fallen person. Set False to keep the Pi as a silent participant
# (speaker-only mode).
VOICE_MIC_ENABLED = True

# sounddevice device identifiers. None = system default. Use either an int
# index (see `python -m sounddevice` to list devices) or a substring of a
# device name. Names are more robust than indices since indices can shift
# across reboots when USB devices reenumerate.
#
# Defaults match this car's wiring:
#   "USB PnP"    → USB PnP Sound Device (mic, 1 in / 0 out)
#   "UACDemoV1"  → UACDemoV1.0          (speaker, 0 in / 2 out)
VOICE_MIC_DEVICE: int | str | None = "USB PnP"
VOICE_SPEAKER_DEVICE: int | str | None = "UACDemoV1"

# Mic sample rate (Hz). 48000 is the LiveKit standard. 16000 works too and
# saves bandwidth — pick whichever your USB mic supports natively to avoid
# resampling on the Pi.
VOICE_MIC_SAMPLE_RATE = 48000

# Mic capture block size in milliseconds. 20 ms = standard WebRTC frame.
# Smaller = lower latency but more CPU; larger = more jitter resilience.
VOICE_MIC_BLOCK_MS = 20

# Maximum number of mic chunks buffered between PortAudio and the LiveKit
# capture task. ~20 × 20ms = 400ms of headroom. When full, the oldest
# behavior is to drop new chunks (PortAudio keeps running).
VOICE_MIC_QUEUE_MAX = 25
