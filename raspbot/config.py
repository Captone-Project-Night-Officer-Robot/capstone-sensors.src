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

FORWARD_SPEED = 35
TURN_SPEED = 30
SEARCH_TURN_SPEED = 22

CONTROL_DELAY_SEC = 0.03

# Safer default. If line is lost, car stops.
# Set False only after the basic tracking works.
STOP_WHEN_LINE_LOST = True

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
AVOID_DISTANCE_CM = 20.0

# Background polling rate of the ultrasonic thread.
ULTRASONIC_POLL_HZ = 20

# Echo timeout. Longer = more tolerant of slow returns, but slows the poll loop.
ULTRASONIC_TIMEOUT_SEC = 0.03

# Discard readings outside this band — sensor is unreliable there.
ULTRASONIC_MIN_CM = 2.0
ULTRASONIC_MAX_CM = 400.0


# -----------------------------
# IR obstacle sensors (digital, active-low: LOW = obstacle present)
# BCM numbering. BCM 9 = BOARD 21, BCM 10 = BOARD 19, BCM 25 = BOARD 22.
# -----------------------------

# Set IR_ENABLED = False if the IR sensors are not wired on your board,
# or while debugging ultrasonic alone.
IR_ENABLED = True

IR_LEFT_PIN = 9
IR_RIGHT_PIN = 10

# Some Yahboom boards expose an "IR enable" pin that must be driven HIGH.
# Set to None if your board does not have one.
IR_POWER_PIN = 25


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
