"""
Configuration for Raspberry Pi 4B Yahboom Pi4WD white-line tracking car.

Start with default values.
Tune only after camera/vision/motor tests pass.
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
# White line detection settings
# -----------------------------
# White in HSV:
# - high V/value/brightness
# - low S/saturation
#
# If white line is not detected, lower WHITE_VALUE_MIN.
# If background is also detected, increase WHITE_VALUE_MIN.
WHITE_VALUE_MIN = 180

# If colored bright objects are detected, lower this.
WHITE_SATURATION_MAX = 80

# Ignore small noise.
MIN_CONTOUR_AREA = 350

# If line center is within this many pixels from frame center, go forward.
CENTER_TOLERANCE_PX = 25

# Clean noisy mask.
USE_MORPHOLOGY = True


# -----------------------------
# Motor behavior
# -----------------------------

FORWARD_SPEED = 30
TURN_SPEED = 45
SEARCH_TURN_SPEED = 22

# PID gains for steering. The PID converts pixel offset (line_x - frame_x)
# into a wheel-speed correction.
#
# Tuning order:
#   1. Set KI=KD=0. Raise KP until the car holds the line but slightly wobbles.
#   2. Add KD to damp the wobble (start small; high KD makes it twitchy).
#   3. Only add KI if there's persistent off-center drift on straight lines.
#
# Output is clamped to ±STEERING_PID_OUTPUT_LIMIT (wheel-speed units, 0-100).
STEERING_PID_KP = 0.30
STEERING_PID_KI = 0.0
STEERING_PID_KD = 0.05
STEERING_PID_OUTPUT_LIMIT = 35
STEERING_PID_INTEGRAL_LIMIT = 200

CONTROL_DELAY_SEC = 0.03

# If True: stop the car when the line is lost.
# If False: sweep right → left → right → left until the line is found again.
STOP_WHEN_LINE_LOST = False

# Duration of each sweep direction before reversing (seconds).
# Lower = tighter sweep, higher = wider arc.
SEARCH_SWEEP_SEC = 0.4

# If movement direction is wrong, switch these.
INVERT_FORWARD = False
INVERT_STEERING = False


# -----------------------------
# Yahboom Pi4WD GPIO pins
# Based on official 4.Code/python/CarRun.py
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
# BCM numbering. BCM 23 = BOARD 16, BCM 24 = BOARD 18
# (matches Yahboom Raspbot hardware wiring).
# -----------------------------

ULTRASONIC_TRIG = 23
ULTRASONIC_ECHO = 24

# Trigger avoidance when obstacle is closer than this (cm).
AVOID_DISTANCE_CM = 10.0

# Background polling rate of the ultrasonic thread.
ULTRASONIC_POLL_HZ = 20

# Echo timeout. Longer = more tolerant of slow returns, but slows the poll loop.
ULTRASONIC_TIMEOUT_SEC = 0.03

# Discard readings outside this band — sensor is unreliable there.
ULTRASONIC_MIN_CM = 3.0
ULTRASONIC_MAX_CM = 200.0


# -----------------------------
# IR obstacle sensors (digital, active-low: LOW = obstacle present)
# BCM numbering. BCM 9 = BOARD 21, BCM 10 = BOARD 19, BCM 25 = BOARD 22.
# -----------------------------

# Set IR_ENABLED = False if the IR sensors are not wired on your board,
# or while debugging ultrasonic alone.
IR_ENABLED = False

IR_LEFT_PIN = 9
IR_RIGHT_PIN = 10

# Some Yahboom boards expose an "IR enable" pin that must be driven HIGH.
# Set to None if your board does not have one.
IR_POWER_PIN = 25

# Yahboom's official sensors are active-LOW (pin reads LOW when obstacle
# detected). Some 3rd-party IR modules are active-HIGH. Flip this if your
# sensors report "blocked" when nothing is in front of them.
IR_ACTIVE_LOW = True


# -----------------------------
# Avoidance behavior
# -----------------------------

# Master switch — set False to skip sensor init / avoidance entirely.
AVOIDANCE_ENABLED = True

# Short reverse before spin — helps unstick from a wall.
AVOID_BACKUP_SEC = 0.15
AVOID_BACKUP_SPEED = 30

# Spin duration and speed when avoiding.
AVOID_SPIN_SEC = 0.45
AVOID_SPIN_SPEED = 35


# -----------------------------
# Fall detection (remote inference)
# A USB camera on the car is read in a background thread and frames are POSTed
# to the FastAPI server in capstone-falldetection.src (running on your laptop).
# When `falling` is True, the car stops until the fall clears.
# -----------------------------

# Replace with your laptop's IP — the one that runs server.py.
FALL_SERVER_URL = "http://172.20.10.2:8000"

# Which USB camera (cv2.VideoCapture index) to read from.
# Note: the original app.py upscales to 980x740 before YOLO — at 320x240 the
# model often misses people. 640x480 is a good balance for bandwidth vs.
# detection quality.
FALL_USB_CAMERA_INDEX = 0
FALL_CAMERA_WIDTH = 640
FALL_CAMERA_HEIGHT = 480

# Frames per second sent to the server (don't need 30 — fall events are slow).
FALL_TARGET_FPS = 5

# JPEG quality of uploaded frames. 70 is a good size/quality balance.
FALL_JPEG_QUALITY = 70

# Per-request timeout (sec). Increase if your laptop is slow or wifi flaky.
FALL_TIMEOUT_SEC = 2.0

# If the server stops responding for this many seconds, the cached "falling"
# state is forced back to False so the car doesn't sit forever.
FALL_STALE_AFTER_SEC = 3.0
