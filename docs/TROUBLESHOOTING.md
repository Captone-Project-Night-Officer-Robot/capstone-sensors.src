# Troubleshooting

## 1. `ModuleNotFoundError: No module named picamera2`

Install:

```bash
sudo apt install -y python3-picamera2
```

Recreate venv:

```bash
rm -rf .venv
python3 -m venv .venv --system-site-packages
source .venv/bin/activate
pip install -r requirements.txt
```

## 2. `ModuleNotFoundError: No module named RPi`

Install:

```bash
sudo apt install -y python3-rpi.gpio
```

Use venv with system packages:

```bash
python3 -m venv .venv --system-site-packages
```

## 3. Camera window does not open

If using SSH, you may not have graphical display.

Use Raspberry Pi desktop, VNC, or run dry tests without debug window.

Check Pi camera:

```bash
libcamera-hello
```

Check USB camera:

```bash
ls /dev/video*
```

## 4. White line mask is all black

The white line is not being detected.

Edit:

```bash
nano raspbot/config.py
```

Lower:

```python
WHITE_VALUE_MIN = 160
```

## 5. White line mask is almost all white

Too much background is detected.

Increase:

```python
WHITE_VALUE_MIN = 210
```

or decrease:

```python
WHITE_SATURATION_MAX = 50
```

## 6. Car moves opposite direction

Edit:

```bash
nano raspbot/config.py
```

Try:

```python
INVERT_FORWARD = True
```

or:

```python
INVERT_STEERING = True
```

## 7. Car does not move, but no error

Check:
- battery is connected
- motor power switch is on
- `python -m scripts.motor_test` was run
- Raspberry Pi GPIO is enabled
- you are running on Raspberry Pi, not Mac

## 8. Car is too aggressive

Use slower settings:

```python
FORWARD_SPEED = 25
TURN_SPEED = 20
CENTER_TOLERANCE_PX = 35
```
