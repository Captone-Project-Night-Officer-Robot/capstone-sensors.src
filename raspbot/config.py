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
