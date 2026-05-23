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
│   ├── vision/
│   │   ├── camera.py
│   │   ├── white_line_detector.py
│   │   ├── mjpeg_server.py      # live debug view in a browser
│   │   └── fall_detector.py     # USB camera -> remote YOLO server
│   └── voice/
│       └── voice_agent_client.py  # triggers LiveKit voice session
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

# Step 9: Run with remote fall detection

This stops the car whenever a connected USB camera (the second camera on the
car, pointed at people) sees someone falling. YOLO inference runs **on your
laptop**, not on the Pi — far faster than running it on the Pi 4B itself.

## How it works

```text
Pi camera  ─┐
            ├─→  line-follow + obstacle avoidance + motors (main thread)
Sensors    ─┘                ▲
                             │  stop while falling=True
USB camera ─→ JPEG ─HTTP─→ Laptop YOLO server ─JSON─→ Pi (background thread)
                             │
                       /fall.mjpg ─→ laptop browser
```

## A. Start the inference server on your laptop

In **`capstone-falldetection.src`** (on the laptop, not the Pi):

```bash
cd capstone-falldetection.src
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python server.py --model best_falling.pt --port 8000
```

You should see:

```text
Loading best_falling.pt...
Model loaded. Classes: {0: 'fall', 1: 'no_fall'}
Listening on http://0.0.0.0:8000
```

Find your laptop's IP. macOS:

```bash
ipconfig getifaddr en0
```

Linux:

```bash
hostname -I
```

Confirm the server is reachable from another machine on the same network:

```bash
curl http://<laptop-ip>:8000/health
```

Expected: `{"status":"ok","model":"best_falling.pt"}`.

## B. Tell the car where the server lives

On the Pi, edit `raspbot/config.py`:

```python
FALL_SERVER_URL = "http://192.168.1.55:8000"   # <-- your laptop's IP
```

(Or pass `--fall-server http://...` on the command line every time.)

## C. Plug the USB camera into the Pi

Find which video device it is:

```bash
ls /dev/video*
```

Usually `/dev/video0` (index `0`). If you also have the Pi CSI camera attached,
the USB camera may show up at a higher index — set it via `FALL_USB_CAMERA_INDEX`
in `config.py` or pass `--fall-camera-index 2`.

## D. Run the car with fall detection + stream

```bash
source .venv/bin/activate
python -m raspbot.apps.line_follow \
    --camera picamera2 \
    --stream \
    --fall-detection \
    --debug
```

Expected log lines:

```text
[app] MJPEG stream live: open http://<pi-ip>:8080/ in a browser on your laptop.
[app] Obstacle avoidance enabled.
[app] Fall detection ON. Server: http://192.168.1.55:8000
[app] White-line follower started.
```

## E. Open the dashboard

In your laptop browser:

```text
http://<pi-ip>:8080/
```

You'll see **three** live feeds:

```text
┌──────────────────┬──────────────────┬──────────────────┐
│ Annotated        │ White-line mask  │ Fall detection   │
│ (Pi camera)      │                  │ (USB camera)     │
└──────────────────┴──────────────────┴──────────────────┘
```

When a fall is detected, the third panel gets a red banner reading **FALL
DETECTED**, and the car stops. As soon as the person stands up (or the state
goes stale after `FALL_STALE_AFTER_SEC` seconds), the car resumes.

## F. Behavior priority on the car

Higher = wins:

```text
1. Fall detection            → STOP (until cleared)
2. Front ultrasonic < AVOID_DISTANCE_CM → stop + backup + spin
3. Line found                → PID differential drive
4. Line lost + IR triggered  → turn away from blocked side
5. Line lost + no IR signal  → sweep search
```

## G. Troubleshooting

| Symptom | Fix |
|---|---|
| `WARNING: fall detection disabled (USB camera index 0 did not open)` | Plug in the USB camera; check `ls /dev/video*`; pass `--fall-camera-index N` |
| `[fall] server error: ConnectionError` overlay | Server not running, wrong IP, or different network |
| `[fall] server error: ReadTimeout` | Inference too slow → lower `FALL_TARGET_FPS` to 2, or switch to `yolov8n.pt` on the server |
| Car never stops when faking a fall | Lower `--conf` on the server (try `--conf 0.20`) |
| Fall panel always blank | Make sure you passed `--fall-detection` AND `--stream` |
| Both cameras conflict | The USB cam and CSI cam are independent; confirm with `vcgencmd get_camera` for CSI and `ls /dev/video*` for USB |

## H. Run without the car (server-only smoke test)

To test the server alone with the laptop's own webcam:

```bash
# On the laptop
cd capstone-falldetection.src
source .venv/bin/activate
python app.py    # original standalone demo, uses laptop webcam
```

---

# Step 10: Voice agent — talk to the fallen person

When the car is stopped next to a fallen person, it triggers a LiveKit voice
session via the Night Officer agent (`capstone.voice-src`). The agent greets
calmly and stays in conversation until the person stands up.

## How it works

```text
Pi (fall + arrived at 10 cm, held for 1 s)
   │
   ├─ POST /api/v1/session/start  →  laptop voice API on port 8001
   │                                  returns { token, room_name, livekit_url }
   ▼
Pi joins LiveKit room (silent participant for now)
   │
   ▼
Voice worker dispatches NightOfficerAgent into that room
   │   Krisp BVC → Silero VAD → Eleven STT → Groq Llama → Eleven TTS
   ▼
TTS audio is published into the room (and will play through the Pi speaker
once audio I/O is wired in Phase 2).

When `falling=False` is observed for 3 s → Pi ends the session → resumes line.
```

## Phase 1 vs Phase 2

| Phase | What works | What's needed |
|---|---|---|
| **Phase 1 (now)** | API trigger + LiveKit room connection + worker dispatch + agent enters room | `pip install livekit` on the Pi. Verifies whole pipeline; no audible audio yet. |
| **Phase 2 (when mic + speaker are wired)** | Live two-way voice conversation | Add `sounddevice`, wire `AudioSource` (mic) and audio-frame routing (speaker). |

## A. Run the voice server on your laptop

In a third terminal on the laptop:

```bash
cd capstone.voice-src
source .venv/bin/activate

# FastAPI HTTP service (mints LiveKit tokens):
uvicorn src.main:app --port 8001

# In another laptop terminal — the agent worker:
python -m src.worker dev    # or `console` for local mic test
```

Make sure `.env` in `capstone.voice-src` has valid keys:
`LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `GROQ_API_KEY`,
`ELEVEN_API_KEY`, `ELEVEN_VOICE_ID`.

## B. Tell the car where the voice API lives

Edit `raspbot/config.py`:

```python
VOICE_API_URL = "http://192.168.1.55:8001"   # ← your laptop's IP, port 8001
VOICE_ROBOT_ID = "raspbot-01"
```

## C. Install LiveKit on the Pi (one time)

```bash
source .venv/bin/activate
pip install livekit
```

If you skip this step, the trigger still fires and logs the session, but the
Pi never joins the room, so the agent isn't dispatched.

## D. Run the car with everything on

```bash
source .venv/bin/activate
python -m raspbot.apps.line_follow \
    --camera picamera2 \
    --stream \
    --fall-detection \
    --voice \
    --debug
```

Expected log when a fall is detected and the car arrives:

```text
[fall→approach dist=42.3cm offset=-12]
[fall→approach dist=18.1cm offset=+2]
[fall→arrived dist=9.7cm]
[fall→arrived dist=9.6cm]
[voice] session started  room=raspbot-01-3f4a8b91  url=wss://...
[voice] room CONNECTED (raspbot-01-3f4a8b91)
[fall→arrived dist=9.6cm]  voice=ON
[voice] holding (room=raspbot-01-3f4a8b91)
[voice] holding (room=raspbot-01-3f4a8b91)
...
[voice] session ended  room=raspbot-01-3f4a8b91     ← person stood up for 3 s
[app] frame=... action=forward                       ← resumes line-follow
```

## E. Tuning

```python
VOICE_TRIGGER_STOP_SECONDS     = 1.0   # how long to be stopped before talking
VOICE_END_AFTER_NO_FALL_SECONDS = 3.0  # how long after fall clears to disconnect
```

## F. Troubleshooting

| Symptom | Fix |
|---|---|
| `[voice] livekit SDK not installed` | `pip install livekit` on the Pi |
| `[voice] session start FAILED: ConnectionError` | voice API not running, wrong port, or laptop on different network |
| `[voice] join-room FAILED: ...` | check `LIVEKIT_URL` in `capstone.voice-src/.env` — must be reachable from the Pi |
| Agent doesn't greet (worker logs show "no participants") | Pi joined but didn't publish — that's expected in Phase 1. The worker may still greet; you just won't hear it without a speaker. |
| Voice keeps starting then stopping | Lower `VOICE_TRIGGER_STOP_SECONDS` or raise `VOICE_END_AFTER_NO_FALL_SECONDS` |

## G. Behavior with all features on (final priority order)

```text
1. Voice session active            → STAY parked (don't drive away mid-conversation)
2. Fall detected (USB cam + YOLO)
     • dist  > 10 cm                → APPROACH (steer to bbox)
     • dist ≤ 10 cm  + held 1 s     → STOP & trigger voice session
3. Standing person + dist ≤ 30 cm   → STOP & wait
4. Line found + obstacle ≤ 15 cm    → STOP & wait
5. Line found + clear               → PID drive
6. Line lost                        → IR-biased sweep
```

---

# Step 11: Hear the voice agent through your laptop (no Pi speaker needed)

The car triggers a LiveKit session and the worker starts speaking via TTS into
that room — but until the Pi has its own speaker, **the audio comes out of
your laptop instead** via a separate listener process.

## How it works

```text
Pi (silent participant) ─┐
                         │
Worker (TTS publisher) ──┼─→  LiveKit Cloud room
                         │
listen_local.py  ←───────┘    (subscribe-only, plays through laptop speakers)
   ▲
   │ polls every 2 s
   ▼
GET /api/v1/session/active  →  list of active rooms
```

## Install audio prerequisites (laptop, one-time)

```bash
# macOS
brew install portaudio

# Linux
sudo apt install libportaudio2
```

Then in `capstone.voice-src`:
```bash
source .venv/bin/activate
pip install sounddevice
```

(Already in `requirements.txt`, so a fresh `pip install -r requirements.txt`
will pick it up.)

## Run the listener — 4th terminal on the laptop

```bash
cd ~/Desktop/workspace/capstone/capstone.voice-src
source .venv/bin/activate
python -m src.listen_local
```

Expected output:
```text
[listen] LiveKit URL : wss://...livekit.cloud
[listen] Voice API   : http://localhost:8001
[listen] Polling every 2.0s for new rooms
```

When the car triggers a fall session:
```text
[listen] new room discovered: raspbot-01-b1f32be7
[listen] joined raspbot-01-b1f32be7
[listen] audio track from agent-xxx in raspbot-01-b1f32be7
[listen] output stream started 48000Hz x1ch (raspbot-01-b1f32be7)
```

→ Your laptop speakers play the Night Officer greeting. 🔊

When the fall clears and the Pi disconnects:
```text
[listen] participant left raspbot-01-b1f32be7: raspbot-01
[listen] room disconnected: raspbot-01-b1f32be7
[listen] room raspbot-01-b1f32be7 cleaned up
```

The listener stays alive and waits for the next session.

## Full 4-terminal layout for a demo

| Terminal | Where | Command |
|---|---|---|
| 1 | Laptop | `cd capstone-falldetection.src && python server.py --model best_falling.pt --port 8000` |
| 2 | Laptop | `cd capstone.voice-src && python -m src.main` (voice API, port 8001) |
| 3 | Laptop | `cd capstone.voice-src && python -m src.worker dev` |
| 4 | **Laptop** | `cd capstone.voice-src && python -m src.listen_local`  ← NEW |
| 5 | Pi SSH | `python -m raspbot.apps.line_follow --camera picamera2 --stream --fall-detection --voice --debug` |

## Troubleshooting

| Symptom | Fix |
|---|---|
| `sounddevice import failed` | Run `brew install portaudio` (macOS) or `apt install libportaudio2`, then `pip install sounddevice` |
| `missing env vars: LIVEKIT_URL ...` | `.env` not in `capstone.voice-src/` root, or values are blank |
| `poll error: ConnectionRefused` | The voice API (`python -m src.main`) isn't running |
| Listener joins room but no audio | The worker hasn't dispatched yet — confirm Terminal 3 is running |
| Choppy audio | Other Mac apps fighting for the audio device, or laptop is bandwidth-constrained. Lower `FALL_TARGET_FPS` on the Pi (less CPU contention) |
| Multiple listeners running | They'll **both** join the room and **both** play audio — close one. |

## When the Pi speaker arrives, do you stop using this?

Up to you — both can coexist (multiple subscribers per room is fine in
LiveKit). Once Phase 2 wires Pi audio playback, kill `listen_local.py` for
realism, or keep it as an "operator overhear" channel.

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
python -m raspbot.apps.line_follow --camera picamera2 --stream --fall-detection
```

Do not run the real car before camera, vision, sensor, and motor tests pass.
