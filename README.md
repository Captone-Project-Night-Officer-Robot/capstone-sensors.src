# Capstone Sensors RC Car - White Line Follower

Clean modular Raspberry Pi 4B RC car project.

This version does **not** use `.env` for the motor driver path.

The motor driver is expected locally at:

```text
robot_side/motor_driver/YB_Pcb_Car.py
```

The project imports it directly from:

```python
from robot_side.motor_driver.YB_Pcb_Car import YB_Pcb_Car
```

## Important motor-driver note

I included a local placeholder file:

```text
robot_side/motor_driver/YB_Pcb_Car.py
```

Because your Raspberry Pi did not have the real `YB_Pcb_Car.py` file installed.

Before real motor movement works, replace that placeholder with the official Yahboom/Raspbot `YB_Pcb_Car.py` driver for your motor board.

You do **not** need to set `YB_PCB_CAR_PATH` after replacing it.

## Project structure

```text
.
├── main.py
├── requirements.txt
├── raspbot/
│   ├── config.py
│   ├── hardware/
│   │   ├── camera.py
│   │   ├── ir_sensors.py
│   │   ├── motor.py
│   │   └── ultrasonic.py
│   ├── navigation/
│   │   └── line_follower.py
│   ├── vision/
│   │   ├── green_lane_detector.py
│   │   └── types.py
│   └── apps/
│       ├── run_line_follower.py
│       ├── test_camera.py
│       ├── test_ir.py
│       ├── test_motors.py
│       └── test_ultrasonic.py
└── robot_side/
    └── motor_driver/
        └── YB_Pcb_Car.py
```

## Setup

```bash
cd /home/workspace/capstone-sensors.src

python3 -m venv .venv
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
```

If `picamera2` or `RPi.GPIO` fails through pip, install them with apt:

```bash
sudo apt update
sudo apt install -y python3-picamera2 python3-rpi.gpio python3-opencv
```

## Replace local motor driver

Put the real driver here:

```bash
cp /path/to/official/YB_Pcb_Car.py robot_side/motor_driver/YB_Pcb_Car.py
```

Check:

```bash
ls -la robot_side/motor_driver/YB_Pcb_Car.py
head -40 robot_side/motor_driver/YB_Pcb_Car.py
```

It must contain:

```python
class YB_Pcb_Car:
```

## Test commands

Dry motor test:

```bash
python -m raspbot.apps.test_motors --dry-run
```

Real motor test:

```bash
python -m raspbot.apps.test_motors
```

Camera + white line detection:

```bash
python -m raspbot.apps.test_camera
```

IR sensor test:

```bash
python -m raspbot.apps.test_ir
```

Ultrasonic test:

```bash
python -m raspbot.apps.test_ultrasonic
```

## Run white-line follower

Dry run:

```bash
python main.py --dry-run --show
```

Real robot, safe speed:

```bash
python main.py --forward-speed 30 --turn-speed 25 --show
```

Headless:

```bash
python main.py --forward-speed 30 --turn-speed 25 --no-window
```

## White line tuning

White detection is configured in:

```text
raspbot/config.py
```

Main values:

```python
lower_white_v = 170
upper_white_s = 80
```

If the room is dark, lower brightness threshold:

```python
lower_white_v = 140
```

If shiny floor is detected as white line, reduce saturation threshold:

```python
upper_white_s = 50
```
