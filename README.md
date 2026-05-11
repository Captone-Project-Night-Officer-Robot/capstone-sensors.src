# Raspbot Raspberry Pi 4B Line Follower

Clean modular RC car navigation codebase for a Raspberry Pi 4B robot using:

- `YB_Pcb_Car` motor driver
- PiCamera2 camera
- OpenCV lane / line detection
- IR side obstacle sensors
- Ultrasonic front distance sensor
- Safe class-based navigation controller

This project refactors the prototype scripts into a maintainable structure.

---

## 1. Project Structure

```text
raspbot_line_follower_clean/
├── README.md
├── requirements.txt
├── .env.example
├── main.py
├── raspbot/
│   ├── __init__.py
│   ├── config.py
│   ├── hardware/
│   │   ├── __init__.py
│   │   ├── camera.py
│   │   ├── ir_sensors.py
│   │   ├── motor.py
│   │   └── ultrasonic.py
│   ├── navigation/
│   │   ├── __init__.py
│   │   └── line_follower.py
│   ├── vision/
│   │   ├── __init__.py
│   │   ├── green_lane_detector.py
│   │   └── types.py
│   └── apps/
│       ├── __init__.py
│       ├── run_line_follower.py
│       ├── test_camera.py
│       ├── test_ir.py
│       ├── test_motors.py
│       └── test_ultrasonic.py
```

---

## 2. Hardware Assumptions

Default pin configuration uses `GPIO.BOARD` mode.

| Device | Pin |
|---|---:|
| Ultrasonic Trig | 16 |
| Ultrasonic Echo | 18 |
| Left IR Sensor | 21 |
| Right IR Sensor | 19 |
| IR Sensor Power / Enable | 22 |

Default motor driver import assumes your original path:

```text
/home/farmscout/Raspbot/2.Hardware Control course/02.Drive motor
```

You can override this path with:

```bash
export YB_PCB_CAR_PATH="/your/path/to/02.Drive motor"
```

---

## 3. Install System Packages

On Raspberry Pi OS:

```bash
sudo apt update
sudo apt install -y python3-pip python3-venv python3-opencv libcamera-apps
```

PiCamera2 is usually installed through Raspberry Pi OS packages. If missing:

```bash
sudo apt install -y python3-picamera2 python3-rpi.gpio
```

---

## 4. Create Virtual Environment

```bash
cd raspbot_line_follower_clean

python3 -m venv .venv
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
```

If `picamera2` or `RPi.GPIO` fails through pip, install them through `apt` as shown above.

---

## 5. Configure Environment

Copy the example file:

```bash
cp .env.example .env
```

Optional:

```bash
export YB_PCB_CAR_PATH="/home/farmscout/Raspbot/2.Hardware Control course/02.Drive motor"
```

---

## 6. Test Hardware One by One

### Test Motors

Dry-run without moving the robot:

```bash
python -m raspbot.apps.test_motors --dry-run
```

Real motor test:

```bash
python -m raspbot.apps.test_motors
```

### Test Ultrasonic Sensor

```bash
python -m raspbot.apps.test_ultrasonic
```

### Test IR Sensors

```bash
python -m raspbot.apps.test_ir
```

### Test Camera

```bash
python -m raspbot.apps.test_camera
```

---

## 7. Run the Line Follower

Dry-run with camera and sensor decisions printed, but no real motor movement:

```bash
python main.py --dry-run --show
```

Real robot run:

```bash
python main.py --show
```

Headless run without OpenCV window:

```bash
python main.py --no-window
```

Safe lower-speed run:

```bash
python main.py --forward-speed 35 --turn-speed 30 --no-window
```

---

## 8. Navigation Priority

The controller decides in this order:

1. Emergency front obstacle protection.
2. Front caution zone.
3. IR side obstacle avoidance.
4. Camera lane following.
5. Fallback behavior when no lane is detected.

Physical safety overrides camera decisions.

---

## 9. Default Behavior

| Condition | Action |
|---|---|
| Front distance `< emergency_stop_cm` | Stop |
| Front distance `< caution_cm` | Slow forward |
| Left IR detects obstacle | Steer right |
| Right IR detects obstacle | Steer left |
| Lane centered | Forward |
| Lane center too far left | Steer left |
| Lane center too far right | Steer right |
| No lane detected | Slow forward or stop, depending on config |

---

## 10. Tuning Values

Most important values are in `raspbot/config.py`:

```python
forward_speed = 45
turn_speed = 35
slow_speed = 25
emergency_stop_cm = 10.0
caution_cm = 20.0
lane_center_tolerance_px = 25
```

For a small RC car, start slow. Increase speeds only after the robot is stable.

---

## 11. Common Problems

### `ModuleNotFoundError: No module named YB_Pcb_Car`

Set the motor driver path:

```bash
export YB_PCB_CAR_PATH="/home/farmscout/Raspbot/2.Hardware Control course/02.Drive motor"
```

Or edit `.env`.

### Camera does not open

Check camera detection:

```bash
libcamera-hello
```

If it fails, enable camera support in Raspberry Pi configuration.

### OpenCV window does not show

Use headless mode:

```bash
python main.py --no-window
```

### Robot moves in the wrong turn direction

Swap left/right motor values in `raspbot/hardware/motor.py`, or invert steering in `raspbot/navigation/line_follower.py`.

---

## 12. Development Notes

This codebase intentionally separates:

- hardware drivers
- computer vision
- navigation decision logic
- runnable apps/tests

Do not put all logic into `main.py`. Keep `main.py` thin and reusable.
