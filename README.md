# Raspberry Pi 4B Yahboom Pi4WD White-Line Tracking Car

This is the final source code for your **Yahboom Raspberry Pi 4WD car** using **Raspberry Pi 4B** and camera-based **white-line tracking**.

Your official Yahboom package has:

```text
4.Code/python/CarRun.py
```

So this project does **not** require `YB_Pcb_Car.py`.

This project uses the same motor GPIO pin layout as Yahboom `CarRun.py`:

```python
IN1 = 20
IN2 = 21
IN3 = 19
IN4 = 26
ENA = 16
ENB = 13
```

---

# What this project does

The car follows a **white line / white tape** on a darker floor, and
**avoids obstacles** using ultrasonic + dual IR sensors as an override layer.

```text
Camera frame ─→ detect white line ─→ line action ─┐
                                                  ├─→ motor
Ultrasonic + IR ─→ avoid decision ────────────────┘
                  (overrides line action when blocked)
```

Per frame:

```text
1. Read ultrasonic distance (latest sample from background thread)
2. Read both IR sensors
3. If distance < AVOID_DISTANCE_CM or either IR is blocked:
       stop → short reverse → spin away from obstacle → resume
   else:
       run normal white-line tracking
```

---

# Project structure

```text
capstone-sensors.src/
├── README.md
├── requirements.txt
├── docs/
│   └── TROUBLESHOOTING.md
├── raspbot/
│   ├── config.py
│   ├── apps/
│   │   └── line_follow.py
│   ├── hardware/
│   │   ├── motor.py
│   │   ├── YB_Pcb_Car.py
│   │   ├── ultrasonic.py        # HC-SR04, background-thread polling
│   │   ├── ir_sensors.py        # dual IR (active-low)
│   │   └── avoider.py           # fuses sensors + override layer
│   └── vision/
│       ├── camera.py
│       ├── white_line_detector.py
│       └── mjpeg_server.py      # live debug view in a browser
└── scripts/
    ├── camera_test.py
    ├── clone_yahboom_repo.sh
    ├── install_pi.sh
    ├── motor_test.py
    ├── show_yahboom_pins.py
    ├── vision_test.py
    └── avoid_test.py            # sensors-only, no motors
```

---

# Option A — Recommended: use this project directly

Use this option first. It is simpler and does not require copying Yahboom files.

## Step 1: Copy/unzip project on Raspberry Pi

```bash
cd
unzip capstone-sensors.src.zip
cd capstone-sensors.src
```

## Step 2: Install dependencies

You can run the install script:

```bash
bash scripts/install_pi.sh
```

Or manually:

```bash
sudo apt update
sudo apt install -y python3-pip python3-venv python3-opencv python3-picamera2 python3-rpi.gpio git

python3 -m venv .venv --system-site-packages
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Why `--system-site-packages`?

Because `picamera2` and `RPi.GPIO` are usually installed by `apt`, not by `pip`.

---

# Step 3: Test camera

For Raspberry Pi Camera Module:

```bash
source .venv/bin/activate
python -m scripts.camera_test --camera picamera2
```

For USB camera:

```bash
source .venv/bin/activate
python -m scripts.camera_test --camera usb --camera-index 0
```

Press `q` to quit.

---

# Step 4: Test white-line detection only

This does **not** move motors.

```bash
source .venv/bin/activate
python -m scripts.vision_test --camera picamera2
```

You will see two windows:

```text
vision-test
white-line-mask
```

In `white-line-mask`:

```text
white line should be white
background should be mostly black
```

If the white line is not detected, tune `raspbot/config.py`.

---

# Step 4b: Test obstacle sensors only

This does **not** move motors. Confirms wiring of HC-SR04 + IR sensors.

```bash
source .venv/bin/activate
python -m scripts.avoid_test
```

Expected output every 0.2 s:

```text
clear    distance=  87.4 cm   IR L=0 R=0
clear    distance=  42.1 cm   IR L=0 R=0
BLOCKED  distance=  12.8 cm   IR L=0 R=0
BLOCKED  distance=  35.7 cm   IR L=1 R=0
```

Quick sanity checks:
- Wave your hand 10 cm in front of the sensor → `BLOCKED ... distance=~10 cm`
- Cover the **left** IR → `IR L=1 R=0`
- Cover the **right** IR → `IR L=0 R=1`

If `distance` is always `inf`, check `TRIG`/`ECHO` wiring or BCM pin numbers in `config.py`.
If IR `L`/`R` are stuck on `1`, your sensor pots are too sensitive — turn them down.

---

# Step 5: Test motors only

Put the car on a box/stand so wheels do not touch the floor.

```bash
source .venv/bin/activate
python -m scripts.motor_test
```

Expected sequence:

```text
Forward
Stop
Spin left
Stop
Spin right
Stop
Back
Final stop
```

If movement direction is wrong, edit:

```bash
nano raspbot/config.py
```

Then change:

```python
INVERT_FORWARD = False
INVERT_STEERING = False
```

Examples:

```python
INVERT_FORWARD = True
```

or:

```python
INVERT_STEERING = True
```

---

# Step 6: Full tracking test without motor movement

This is the safest full test.

```bash
source .venv/bin/activate
python -m raspbot.apps.line_follow --camera picamera2 --dry-run --debug
```

The terminal will print motor commands, but wheels will not move.

Example:

```text
[motor] forward speed=35
[motor] spin_left speed=30
[motor] spin_right speed=30
[motor] stop
```

---

# Step 7: Run real car

Put the car on the white-line track.

```bash
source .venv/bin/activate
python -m raspbot.apps.line_follow --camera picamera2
```

If obstacle sensors are wired, avoidance is **on by default**. To bypass it:

```bash
python -m raspbot.apps.line_follow --camera picamera2 --no-avoidance
```

Stop:

```bash
Ctrl+C
```

---

# Step 8: Watch the camera from your laptop (MJPEG stream)

When you SSH into the Pi headless, `cv2.imshow` can't show anything on your
laptop. The app can instead serve the debug view over HTTP so you can open it
in any browser.

## Start with streaming enabled

On the Pi (over SSH):

```bash
source .venv/bin/activate
python -m raspbot.apps.line_follow --camera picamera2 --stream
```

You will see:

```text
[app] MJPEG stream live: open http://<pi-ip>:8080/ in a browser on your laptop.
```

## Find the Pi's IP

On the Pi:

```bash
hostname -I
```

Example output:

```text
192.168.1.42
```

## Open it on your laptop

In any browser:

```text
http://192.168.1.42:8080/
```

You'll see two side-by-side feeds:

```text
left   → annotated video (line center, deadband, action overlay)
right  → white-line mask (what the detector sees)
```

Direct stream URLs (useful for OBS / VLC / `curl`):

```text
http://192.168.1.42:8080/stream.mjpg   → annotated
http://192.168.1.42:8080/mask.mjpg     → mask
```

## Options

```bash
# Different port:
python -m raspbot.apps.line_follow --camera picamera2 --stream --stream-port 9000

# Reduce bandwidth (drop stream FPS):
python -m raspbot.apps.line_follow --camera picamera2 --stream --stream-fps 8

# Stream + console debug logs at the same time:
python -m raspbot.apps.line_follow --camera picamera2 --stream --debug
```

## Notes

- The stream is opt-in. Skip `--stream` for competition runs.
- The Pi and your laptop must be on the same Wi-Fi network.
- The control loop runs at full speed regardless of `--stream-fps`; the cap
  only limits how often frames are pushed to viewers.
- Multiple browser tabs / viewers can connect simultaneously.

---

---

# Option B — Alternative: clone official Yahboom repo

Use this option if you want to compare with the official Yahboom files, confirm `CarRun.py`, or test the original demo.

## Step 1: Clone official repo

From anywhere:

```bash
cd
git clone https://github.com/YahboomTechnology/RaspberryPi-4WD-Car.git
```

Or use the script included here:

```bash
bash scripts/clone_yahboom_repo.sh
```

## Step 2: Check official Python folder

```bash
cd/RaspberryPi-4WD-Car/4.Code/python
ls
```

You should see:

```text
CarRun.py
tracking.py
infrared_follow.py
light_follow.py
...
```

## Step 3: Check motor pins from official `CarRun.py`

From this project folder:

```bash
cd/capstone-sensors.src
source .venv/bin/activate
python -m scripts.show_yahboom_pins --repo/RaspberryPi-4WD-Car
```

Expected pin values:

```text
IN1 = 20
IN2 = 21
IN3 = 19
IN4 = 26
ENA = 16
ENB = 13
```

## Important warning about official `CarRun.py`

Do **not** import official `CarRun.py` inside our app directly.

Some Yahboom demo files are written as runnable demos and may move the car when executed/imported.

This project already includes safe direct GPIO motor code in:

```text
raspbot/hardware/motor.py
```

So cloning the official repo is only for reference/checking, not required for running our tracker.

---

# Option C — Alternative camera usage

## Raspberry Pi Camera

```bash
python -m raspbot.apps.line_follow --camera picamera2
```

## USB camera

```bash
python -m raspbot.apps.line_follow --camera usb --camera-index 0
```

If USB index 0 does not work:

```bash
ls /dev/video*
```

Then try:

```bash
python -m scripts.camera_test --camera usb --camera-index 1
```

---

# Tuning guide

Open config:

```bash
nano raspbot/config.py
```

Main values:

```python
WHITE_VALUE_MIN = 180
WHITE_SATURATION_MAX = 80
CENTER_TOLERANCE_PX = 25
FORWARD_SPEED = 35
TURN_SPEED = 30
STOP_WHEN_LINE_LOST = True
```

## White line is not detected

Lower this:

```python
WHITE_VALUE_MIN = 160
```

Try:

```text
150
160
170
180
```

## Background is also detected as white

Increase this:

```python
WHITE_VALUE_MIN = 200
```

Try:

```text
190
200
210
220
```

## Bright colored objects are detected

Lower saturation max:

```python
WHITE_SATURATION_MAX = 50
```

Try:

```text
40
50
60
80
```

## Car shakes left/right

Increase tolerance:

```python
CENTER_TOLERANCE_PX = 35
```

or lower turn speed:

```python
TURN_SPEED = 22
```

## Car is too fast

Lower speed:

```python
FORWARD_SPEED = 25
```

## Line lost behavior

Safer mode:

```python
STOP_WHEN_LINE_LOST = True
```

Search mode:

```python
STOP_WHEN_LINE_LOST = False
```

If search mode is enabled, the car slowly rotates when it loses the line.

---

# Obstacle avoidance tuning

All knobs live in `raspbot/config.py`.

## Pins (BCM numbering)

```python
ULTRASONIC_TRIG = 23   # BOARD 16
ULTRASONIC_ECHO = 24   # BOARD 18
IR_LEFT_PIN     = 9    # BOARD 21
IR_RIGHT_PIN    = 10   # BOARD 19
IR_POWER_PIN    = 25   # BOARD 22  (set None if your board has no enable pin)
```

These match the Yahboom Raspbot hardware wiring used in courses 04–06.

## Thresholds

```python
AVOID_DISTANCE_CM   = 20.0   # closer than this → trigger avoidance
ULTRASONIC_POLL_HZ  = 20     # background sampling rate
```

Car stops too late → increase `AVOID_DISTANCE_CM` to 25–30.
Car twitches on every wall → decrease to 12–15.

## Maneuver

```python
AVOID_BACKUP_SEC   = 0.15
AVOID_BACKUP_SPEED = 30
AVOID_SPIN_SEC     = 0.45
AVOID_SPIN_SPEED   = 35
```

Spin doesn't clear the obstacle → increase `AVOID_SPIN_SEC` to 0.7–1.0.
Car over-rotates and loses the line → decrease `AVOID_SPIN_SEC`.

## Switches

```python
AVOIDANCE_ENABLED = True
```

Set `False` to globally disable (or pass `--no-avoidance` on the CLI).

## How it integrates

`avoider.evaluate()` runs **before** the line-follow action each frame:

```text
distance < AVOID_DISTANCE_CM  → blocked
left IR blocked only          → spin right
right IR blocked only         → spin left
both IR / ultrasonic only     → spin right (default)
```

When blocked, the avoider runs a small maneuver (~0.6 s total) and the next
frame resumes line-following. The camera is not read during the maneuver —
that's intentional.

---

# Recommended first run order

Run in this exact order:

```bash
cd/capstone-sensors.src
source .venv/bin/activate

python -m scripts.camera_test --camera picamera2
python -m scripts.vision_test --camera picamera2
python -m scripts.avoid_test
python -m scripts.motor_test
python -m raspbot.apps.line_follow --camera picamera2 --dry-run --debug
python -m raspbot.apps.line_follow --camera picamera2
python -m raspbot.apps.line_follow --camera picamera2 --stream   # view from laptop
```

Do not run the real car before camera, vision, sensor, and motor tests pass.
