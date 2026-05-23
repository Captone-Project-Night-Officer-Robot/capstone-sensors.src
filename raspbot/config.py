"""
Configuration for the Yahboom Pi4WD line-follower robot.

Behavior priority (highest first):
  1. Voice session active        → STAY parked (don't drive mid-conversation)
  2. Fall detected               → STOP immediately, trigger voice session
  3. Obstacle within OBSTACLE_DISTANCE_CM → STOP, then turn right by
     OBSTACLE_TURN_DEGREES to dodge around it (repeats while obstacle present)
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

# Fix exposure on the Pi camera (picamera2). When True, auto-exposure is
# disabled and CAMERA_EXPOSURE_TIME_US / CAMERA_ANALOGUE_GAIN are forced.
# Use this when glare / sunlight makes the sensor blow out and the line
# detector loses contrast. Tune by running scripts.vision_test and
# adjusting until the white line stays bright but the background does
# NOT push V > WHITE_VALUE_MIN.
#
# Typical starting points:
#   Bright outdoor / direct sunlight : 2000-4000 µs, gain 1.0
#   Indoor fluorescent / daylight    : 6000-10000 µs, gain 1.0-2.0
#   Dim indoor                       : 15000-25000 µs, gain 2.0-4.0
CAMERA_FIX_EXPOSURE = False
CAMERA_EXPOSURE_TIME_US = 8000
CAMERA_ANALOGUE_GAIN = 1.0

# Size of the debug visualisation windows (pixels). The camera frame is
# upscaled to this size for display only — control logic still runs on the
# original CAMERA_WIDTH x CAMERA_HEIGHT frame.
DEBUG_WINDOW_WIDTH = 800
DEBUG_WINDOW_HEIGHT = 600

# Use only the lower portion of the image. 0.55 = ignore top 55%, use
# bottom 45%. Narrower ROI = less far-away ceiling lights / floor glare
# in view, more reliable line lock at the cost of shorter look-ahead.
# Raise toward 0.75 if glare from far away keeps fooling the detector;
# lower toward 0.5 if a close-up line registers as a fat blob rather
# than a long strip and gets rejected by the aspect-ratio filter.
ROI_TOP_RATIO = 0.55


# -----------------------------
# White line detection
# -----------------------------
# White in HSV = high V (brightness), low S (saturation).
# Lower WHITE_VALUE_MIN if the line isn't detected.
# Raise it if background light is detected as white.
WHITE_VALUE_MIN = 200

# Lower if bright colored objects (sunlight tint, fluorescent glow) are
# detected as the line. Pure white tape sits at near-zero saturation.
WHITE_SATURATION_MAX = 60

# Ignore small noise contours.
MIN_CONTOUR_AREA = 350

# Reject blobs larger than this fraction of the ROI — they're a wall,
# whole-floor reflection, or huge glare patch, not a line. 0.0 disables.
LINE_MAX_AREA_RATIO = 0.5

# Require contours to be line-shaped: the rotated bounding rect's longer
# side must be at least this many times the shorter side. A piece of
# white tape viewed from above is typically 3-6×; glare blobs are < 2×.
# Lower this if the robot loses the line on tight curves or when the line
# is close to the camera (it foreshortens to a fat blob); raise it if
# round glare patches still pass through.
LINE_ASPECT_RATIO_MIN = 0

# If the line center is within this many pixels of frame center, drive straight.
CENTER_TOLERANCE_PX = 25

# Morphological open/close on the mask.
USE_MORPHOLOGY = True


# -----------------------------
# Motor behavior
# -----------------------------

# NOTE: on a real floor with the chassis loaded, anything under ~45 tends
# not to break static friction — the wheels spin freely when the car is
# lifted but the car won't actually move forward on the ground.
# FORWARD_SPEED must also be > STEERING_PID_OUTPUT_LIMIT, otherwise the
# slow wheel during a steering correction gets commanded to 0 and stalls.
FORWARD_SPEED = 35
TURN_SPEED = 40
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
# STOPS and rotates right by OBSTACLE_TURN_DEGREES to dodge the obstacle.
# If the obstacle is still in range after the turn, the maneuver repeats
# (so two ticks = 120°, three = 180°, etc.) until the path is clear.
OBSTACLE_DISTANCE_CM = 20.0

# How far the robot rotates on each obstacle hit. 60° is the spec default.
OBSTACLE_TURN_DEGREES = 60

# Wheel speed used during the obstacle-dodge spin. Higher = quicker turn
# but more wheel slip on slick floors. Independent of TURN_SPEED so it
# can be tuned separately.
OBSTACLE_TURN_SPEED = 40

# Seconds the robot must spin in place at OBSTACLE_TURN_SPEED to rotate
# 1 degree. Used to convert OBSTACLE_TURN_DEGREES into a turn duration —
# the Yahboom car has no IMU/encoders so we time the spin.
#
# Calibrate empirically: run a one-shot 360° spin at OBSTACLE_TURN_SPEED
# (e.g. scripts.motor_test), divide the elapsed seconds by 360.
# Default 0.012 → a 60° turn lasts ~0.72 s, which is the right ballpark
# on a fully-charged Raspbot at speed 40 on tile/laminate.
OBSTACLE_TURN_SEC_PER_DEGREE = 0.012


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

# Software gain applied to TTS audio before it reaches the speaker. 1.0 =
# no change. Values above 1.0 amplify; samples that would overflow int16
# (±32767) are clipped (which sounds harsh at extreme settings).
#
# Try in this order if the agent is too quiet:
#   1. Turn up the speaker's physical knob (if it has one).
#   2. `alsamixer -c <UAC card>` → raise PCM/Master to 100%.
#   3. Only then raise this value above 1.0.  1.5–2.0 is usually safe
#      for ElevenLabs TTS; 3.0+ will start to clip on loud syllables.
VOICE_SPEAKER_GAIN = 1.0
