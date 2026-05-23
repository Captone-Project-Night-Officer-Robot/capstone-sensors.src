# Raspberry Pi 4B Yahboom Pi4WD — White-Line Tracking Robot

Production source for the Yahboom Raspberry Pi 4WD car running on a
Raspberry Pi 4B. Camera-based **white-line tracking** with **obstacle stop +
line search**, **remote fall detection** (YOLO on your laptop), and a
**LiveKit voice agent** that talks to a fallen person until help arrives.

---

## Behavior in one picture

Each control-loop frame, the robot picks exactly one state, in this priority
order (highest first):

| # | State      | Trigger                                         | Action                                  |
|---|------------|-------------------------------------------------|-----------------------------------------|
| 1 | `VOICE`    | A voice session is active                       | STAY parked. Don't drive mid-conversation. |
| 2 | `FALL`     | YOLO says someone is falling                    | STOP immediately. Voice agent is triggered. |
| 3 | `OBSTACLE` | Ultrasonic ≤ `OBSTACLE_DISTANCE_CM`             | STOP, then sweep to **search the white line** (find a heading that bypasses the obstacle). |
| 4 | `FOLLOW`   | White line visible                              | PID differential drive along the line.  |
| 5 | `SEARCH`   | White line not visible                          | Alternating left/right sweep until the line is reacquired. |

End-to-end flow the robot performs:

```text
follow line  →  obstacle ahead  →  stop + sweep  →  line found again  →  follow
follow line  →  fall detected   →  stop + voice  →  conversation ends  →  search → follow
```

---

## Project structure

```text
capstone-sensors.src/
├── README.md
├── requirements.txt
├── docs/
│   └── TROUBLESHOOTING.md
├── raspbot/
│   ├── config.py
│   ├── apps/
│   │   └── line_follow.py        # main app + state machine
│   ├── hardware/
│   │   ├── motor.py              # YB_Pcb_Car driver
│   │   ├── ultrasonic.py         # HC-SR04, background-thread polling
│   │   ├── ir_sensors.py         # dual IR (active-low)
│   │   ├── avoider.py            # Sensors aggregator (ultrasonic + IR)
│   │   └── pid.py
│   ├── vision/
│   │   ├── camera.py
│   │   ├── white_line_detector.py
│   │   ├── mjpeg_server.py       # live debug view in a browser
│   │   └── fall_detector.py      # USB camera -> remote YOLO server
│   └── voice/
│       └── voice_agent_client.py # triggers LiveKit voice session
└── scripts/
    ├── camera_test.py
    ├── motor_test.py
    ├── vision_test.py
    ├── avoid_test.py             # sensors-only, no motors
    └── show_yahboom_pins.py
```

---

## Motor pin layout

Matches the official Yahboom `4.Code/python/CarRun.py`:

```python
IN1 = 20
IN2 = 21
IN3 = 19
IN4 = 26
ENA = 16
ENB = 13
```

The Yahboom Raspbot driver IC (STM8 @ I2C `0x16` → AT8236) is wired to I2C,
not directly to GPIO — motor commands go through `YB_Pcb_Car.py`, which lives
at `raspbot/hardware/YB_Pcb_Car.py`.

---

# Install

## 1. Copy the project onto the Pi

```bash
cd
unzip capstone-sensors.src.zip
cd capstone-sensors.src
```

## 2. Install dependencies

Use the install script:

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

`--system-site-packages` is required so the venv can see the `apt`-installed
`picamera2` and `RPi.GPIO`.

---

# Bring-up tests

Run these in order before the first real-car run. Each one isolates one
subsystem so failures point at one piece of hardware.

## 1. Camera

Pi camera:

```bash
source .venv/bin/activate
python -m scripts.camera_test --camera picamera2
```

USB camera:

```bash
python -m scripts.camera_test --camera usb --camera-index 0
```

Press `q` to quit.

## 2. White-line detection (no motors)

```bash
python -m scripts.vision_test --camera picamera2
```

Two windows open: `vision-test` (annotated) and `white-line-mask`. In the
mask, the white line must be white and everything else mostly black. If not,
tune `WHITE_VALUE_MIN` / `WHITE_SATURATION_MAX` in `raspbot/config.py`.

## 3. Obstacle sensors (no motors)

```bash
python -m scripts.avoid_test
```

Expected output (every 0.2 s):

```text
clear    distance=  87.4 cm   IR raw=(L=1,R=1)   blocked=(L=0,R=0)
BLOCKED  distance=  12.8 cm   IR raw=(L=1,R=1)   blocked=(L=0,R=0)
BLOCKED  distance=  35.7 cm   IR raw=(L=0,R=1)   blocked=(L=1,R=0)
```

Quick sanity checks:
- Wave your hand 10 cm in front of HC-SR04 → `BLOCKED  distance=~10 cm`
- Cover left IR → `blocked=(L=1,R=0)`
- Cover right IR → `blocked=(L=0,R=1)`

If `distance` is always `inf`, check `ULTRASONIC_TRIG` / `ULTRASONIC_ECHO`
wiring or BCM pin numbers in `config.py`. If IR readings are stuck on `1`,
turn the sensor pots down.

## 4. Motors (wheels off the floor!)

Put the car on a box. Then:

```bash
python -m scripts.motor_test
```

Expected sequence:

```text
Forward → Stop → Spin left → Stop → Spin right → Stop → Back → Final stop
```

If a direction is wrong, edit `raspbot/config.py`:

```python
INVERT_FORWARD = True    # forward/back swapped
INVERT_STEERING = True   # left/right swapped
```

## 5. Full app, dry-run (safest end-to-end check)

```bash
python -m raspbot.apps.line_follow --camera picamera2 --dry-run --debug
```

Motor commands print but wheels don't move. Expected log lines:

```text
[app] Sensors enabled.
[app] White-line follower started. Stop with Ctrl+C.
[app] frame=0   state=follow   line=found offset=-3   dist=inf
[app] frame=30  state=search   line=lost              dist=inf
[app] frame=60  state=obstacle line=found offset=12   dist=12.4cm
```

---

# Run the real car

## Line-following only

```bash
python -m raspbot.apps.line_follow --camera picamera2
```

Stop with `Ctrl+C`.

Skip sensor init (e.g., HC-SR04 not wired yet):

```bash
python -m raspbot.apps.line_follow --camera picamera2 --no-sensors
```

## Add the MJPEG dashboard (recommended for headless SSH)

```bash
python -m raspbot.apps.line_follow --camera picamera2 --stream
```

You'll see:

```text
[app] MJPEG stream live: open http://<pi-ip>:8080/ in a browser on your laptop.
```

Find the Pi's IP with `hostname -I`, then open `http://<pi-ip>:8080/` on
your laptop. Two side-by-side feeds appear:

```text
left  → annotated video (line center, deadband, action overlay)
right → white-line mask
```

Direct URLs for OBS/VLC/`curl`:

```text
http://<pi-ip>:8080/stream.mjpg   → annotated
http://<pi-ip>:8080/mask.mjpg     → mask
```

Options:

```bash
--stream-port 9000     # different port
--stream-fps 8         # drop stream FPS (control loop is unaffected)
--stream --debug       # stream + console logs
```

---

# Fall detection

This stops the car the moment a separate USB camera (mounted to face people)
sees someone falling. YOLO runs **on your laptop**, not on the Pi.

```text
Pi camera  ──┐
             ├─→  line-follow + obstacle stop + motors      (main thread)
Sensors   ──┘                ▲
                             │  stop while falling=True
USB camera ─→ JPEG ─HTTP─→ Laptop YOLO server ─JSON─→ Pi    (background)
                             │
                       /fall.mjpg ─→ laptop browser
```

## A. Start the YOLO server on the laptop

```bash
cd capstone-falldetection.src
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python server.py --model best_falling.pt --port 8000
```

Expected:

```text
Loading best_falling.pt...
Model loaded. Classes: {0: 'fall', 1: 'no_fall'}
Listening on http://0.0.0.0:8000
```

Find the laptop IP (macOS `ipconfig getifaddr en0`, Linux `hostname -I`),
then sanity-check:

```bash
curl http://<laptop-ip>:8000/health
# {"status":"ok","model":"best_falling.pt"}
```

## B. Point the Pi at the server

`raspbot/config.py`:

```python
FALL_SERVER_URL = "http://192.168.1.55:8000"   # ← your laptop IP
```

Or pass `--fall-server http://...` on the CLI.

## C. Plug in the USB camera and pick the index

```bash
ls /dev/video*
```

Pass `--fall-camera-index N` or set `FALL_USB_CAMERA_INDEX = N` in
`config.py`.

## D. Run with fall detection + stream

```bash
python -m raspbot.apps.line_follow \
    --camera picamera2 \
    --stream \
    --fall-detection \
    --debug
```

Expected log:

```text
[app] Sensors enabled.
[app] MJPEG stream live: open http://<pi-ip>:8080/ ...
[app] Fall detection ON. Server: http://192.168.1.55:8000
[app] White-line follower started. Stop with Ctrl+C.
```

The dashboard now shows **three** feeds:

```text
┌──────────────────┬──────────────────┬──────────────────┐
│ Annotated        │ White-line mask  │ Fall detection   │
│ (Pi camera)      │                  │ (USB camera)     │
└──────────────────┴──────────────────┴──────────────────┘
```

When a fall is detected, the third panel gets a **FALL DETECTED** banner and
the car stops immediately. Once the person is up (or YOLO goes stale after
`FALL_STALE_AFTER_SEC`), the car returns to its normal `FOLLOW` / `SEARCH`
behavior.

## Troubleshooting

| Symptom                                                              | Fix                                                                              |
|----------------------------------------------------------------------|----------------------------------------------------------------------------------|
| `WARNING: fall detection disabled (USB camera index 0 did not open)` | Plug in the USB camera; check `ls /dev/video*`; pass `--fall-camera-index N`     |
| `[fall] server error: ConnectionError`                               | Server not running, wrong IP, or different network                               |
| `[fall] server error: ReadTimeout`                                   | Inference too slow → lower `FALL_TARGET_FPS` to 2, or switch to `yolov8n.pt`     |
| Car never stops when faking a fall                                   | Lower `--conf` on the server (try `--conf 0.20`)                                 |
| Fall panel always blank                                              | Pass **both** `--fall-detection` AND `--stream`                                  |

Server-only smoke test (no car):

```bash
cd capstone-falldetection.src
source .venv/bin/activate
python app.py    # standalone demo using the laptop webcam
```

---

# Voice agent

When the car stops on a detected fall, it calls the FastAPI voice server
(`capstone.voice-src`) to mint a LiveKit token, joins the room, and the
worker dispatches the `NightOfficerAgent`. The agent talks to the person
until YOLO has reported `falling=False` for `VOICE_END_AFTER_NO_FALL_SECONDS`.

```text
Pi (state=FALL, debounced VOICE_TRIGGER_STOP_SECONDS)
   │
   ├─ POST /api/v1/session/start  →  voice API on laptop port 8001
   │                                  returns { token, room_name, livekit_url }
   ▼
Pi joins LiveKit room (silent participant in Phase 1)
   │
   ▼
Voice worker dispatches NightOfficerAgent into the room
   │   Krisp BVC → Silero VAD → Eleven STT → Groq Llama → Eleven TTS
   ▼
Agent TTS streams into the room. Pi stays in state=VOICE — motors locked.
   │
   ▼
YOLO reports falling=False for VOICE_END_AFTER_NO_FALL_SECONDS
   │
   ▼
Pi leaves the room. State falls through to SEARCH → FOLLOW.
```

## Phase 1 vs Phase 2

| Phase                    | What works                                              | What's needed                                          |
|--------------------------|---------------------------------------------------------|--------------------------------------------------------|
| **Phase 1 (now)**        | Token mint + LiveKit room connection + worker dispatch  | `pip install livekit` on the Pi. No audio I/O yet.     |
| **Phase 2 (mic+speaker)**| Live two-way voice conversation                         | Add `sounddevice` + AudioSource (mic) + frame routing  |

## A. Run the voice server on the laptop

```bash
cd capstone.voice-src
source .venv/bin/activate

# Terminal 2: FastAPI HTTP service (mints LiveKit tokens):
uvicorn src.main:app --port 8001

# Terminal 3: agent worker:
python -m src.worker dev
```

`capstone.voice-src/.env` must define:
`LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `GROQ_API_KEY`,
`ELEVEN_API_KEY`, `ELEVEN_VOICE_ID`. Keep `.env` **gitignored** — rotate
any key that has been committed.

## B. Point the Pi at the voice API

`raspbot/config.py`:

```python
VOICE_API_URL = "http://192.168.1.55:8001"
VOICE_ROBOT_ID = "raspbot-01"
```

## C. Install LiveKit on the Pi (one-time)

```bash
source .venv/bin/activate
pip install livekit
```

Without this, the session is logged but the Pi never joins the room, so the
worker isn't dispatched.

## D. Run with everything on

```bash
python -m raspbot.apps.line_follow \
    --camera picamera2 \
    --stream \
    --fall-detection \
    --voice \
    --debug
```

Expected log for a fall → voice → resume cycle:

```text
[app] frame=312 state=follow   line=found offset=-2   dist=inf
[app] frame=320 state=fall     line=lost              dist=37.4cm  falling=True
[voice] session started  room=raspbot-01-3f4a8b91  url=wss://...
[voice] room CONNECTED (raspbot-01-3f4a8b91)
[app] frame=340 state=voice    line=lost              dist=37.4cm  falling=True  room=raspbot-01-3f4a8b91
[app] frame=400 state=voice    line=found offset=8    dist=37.4cm  room=raspbot-01-3f4a8b91
...
[voice] session ended  room=raspbot-01-3f4a8b91
[app] frame=820 state=search   line=lost              dist=inf
[app] frame=830 state=follow   line=found offset=-1   dist=inf
```

## Tuning

```python
VOICE_TRIGGER_STOP_SECONDS      = 1.0   # stopped-with-fall debounce before triggering
VOICE_END_AFTER_NO_FALL_SECONDS = 15.0  # falling=False debounce before disconnect
```

## Troubleshooting

| Symptom                                            | Fix                                                                |
|----------------------------------------------------|--------------------------------------------------------------------|
| `[voice] livekit SDK not installed`                | `pip install livekit` on the Pi                                    |
| `[voice] session start FAILED (ConnectionError)`   | Voice API not running, wrong port, or laptop on a different network|
| `[voice] join-room FAILED: ...`                    | Check `LIVEKIT_URL` in `capstone.voice-src/.env`                   |
| Agent doesn't greet                                | Phase 1: no audio I/O on the Pi yet — use `listen_local.py` below  |
| Voice keeps starting then stopping                 | Lower `VOICE_TRIGGER_STOP_SECONDS` or raise `VOICE_END_AFTER_NO_FALL_SECONDS` |

---

# Test the voice agent without the car

Two standalone test modes exist — neither requires the Pi or motors.

## Test mode 1 — `console` (fastest; agent only)

The LiveKit Agents CLI ships a `console` subcommand that runs the agent
locally using your laptop's mic and speakers. No LiveKit room, no FastAPI,
no Pi — pure agent-in / agent-out. Use this to verify STT → LLM → TTS
plumbing in isolation.

```bash
cd capstone.voice-src
source .venv/bin/activate

# .env must define GROQ_API_KEY, ELEVEN_API_KEY, ELEVEN_VOICE_ID at minimum.
# LIVEKIT_URL / LIVEKIT_API_KEY / LIVEKIT_API_SECRET are NOT required here.
python -m src.worker console
```

Expected:

```text
Starting Night Officer agent worker — log level: info
Press [Ctrl+B] to toggle text/audio mode, [Q] to quit.
```

Speak into the laptop mic — the agent should reply through the speakers.
`Ctrl+B` switches to text mode if you prefer typing.

When this works, the agent itself is healthy. Any later failure during a
full run is a LiveKit-room or networking issue, not the agent.

## Test mode 2 — manual session trigger (full pipeline minus the Pi)

This exercises the **exact** path the car uses, but you trigger the session
from a `curl` instead of the Pi. Good for verifying the API, token mint,
worker dispatch, and the laptop listener all work together before bringing
the robot online.

### Step 1 — start the three services (3 laptop terminals)

```bash
# Terminal 1 — FastAPI voice service (mints LiveKit tokens)
cd capstone.voice-src && source .venv/bin/activate
uvicorn src.main:app --port 8001

# Terminal 2 — Agent worker (dispatches the NightOfficerAgent into rooms)
cd capstone.voice-src && source .venv/bin/activate
python -m src.worker dev

# Terminal 3 — Listener (plays room audio through laptop speakers)
cd capstone.voice-src && source .venv/bin/activate
python -m src.listen_local
```

Sanity check the API:

```bash
curl http://localhost:8001/api/v1/health
# {"status":"ok"}
```

### Step 2 — trigger a session by hand

In a 4th terminal:

```bash
curl -X POST http://localhost:8001/api/v1/session/start \
    -H "Content-Type: application/json" \
    -d '{"robot_id": "test-rig"}'
```

Expected response:

```json
{
  "room_name": "test-rig-3f4a8b91",
  "token": "eyJhbGciOiJIUzI1Ni...",
  "livekit_url": "wss://your-project.livekit.cloud"
}
```

What should happen next, in order:

- **Terminal 1** logs `Starting session ... room_name=test-rig-3f4a8b91`.
- **Terminal 2** logs the worker accepting the dispatch and the agent
  joining the room.
- **Terminal 3** logs `new room discovered: test-rig-3f4a8b91`, then
  `audio track from agent-xxx`, then your speakers play the greeting.

### Step 3 — end the session

The session has no Pi-side debounce here, so it stays open until you
explicitly clean it up:

```bash
# Drop it from the active-session registry so the listener stops polling it.
curl -X DELETE http://localhost:8001/api/v1/session/active/test-rig-3f4a8b91
```

To kill the agent worker side, just `Ctrl+C` Terminal 2.

### Inspect active sessions any time

```bash
curl http://localhost:8001/api/v1/session/active
```

### Troubleshooting

| Symptom                                                | Fix                                                                                       |
|--------------------------------------------------------|-------------------------------------------------------------------------------------------|
| `curl: (7) Failed to connect to localhost port 8001`   | Terminal 1 (`uvicorn`) isn't running                                                      |
| API responds but listener never joins                  | Terminal 3 (`listen_local`) not running, or `.env` LIVEKIT_* values blank                 |
| Listener joins room but no audio                       | Terminal 2 (worker) isn't running or hasn't been dispatched — check its logs              |
| `console` mode is silent                               | `GROQ_API_KEY` / `ELEVEN_API_KEY` missing in `.env`; or default audio device isn't routed |
| Different `room_name` each curl                        | Expected — the server auto-generates one. Pass `"room_name": "fixed-test"` in the body to override. |

---

# Hear the voice agent through your laptop (no Pi speaker needed)

Until the Pi has a speaker wired, run the listener on your laptop — it
subscribes to the room and plays audio through your laptop speakers.

```text
Pi (silent participant) ─┐
                         │
Worker (TTS publisher) ──┼─→  LiveKit Cloud room
                         │
listen_local.py  ←───────┘    (subscribe-only, plays via laptop speakers)
```

Prerequisites (one-time):

```bash
# macOS
brew install portaudio
# Linux
sudo apt install libportaudio2

cd capstone.voice-src
source .venv/bin/activate
pip install sounddevice
```

Run (Terminal 4 on the laptop):

```bash
python -m src.listen_local
```

When the car triggers a session, your laptop speakers play the Night
Officer greeting. The listener stays alive between sessions.

## Full 4-terminal demo layout

| # | Where  | Command                                                                                                  |
|---|--------|----------------------------------------------------------------------------------------------------------|
| 1 | Laptop | `cd capstone-falldetection.src && python server.py --model best_falling.pt --port 8000`                  |
| 2 | Laptop | `cd capstone.voice-src && uvicorn src.main:app --port 8001`                                              |
| 3 | Laptop | `cd capstone.voice-src && python -m src.worker dev`                                                      |
| 4 | Laptop | `cd capstone.voice-src && python -m src.listen_local`                                                    |
| 5 | Pi SSH | `python -m raspbot.apps.line_follow --camera picamera2 --stream --fall-detection --voice --debug`        |

---

# Tuning

All knobs live in `raspbot/config.py`.

## Line detection

```python
WHITE_VALUE_MIN      = 180   # lower → easier to detect; raise → less false-positives
WHITE_SATURATION_MAX = 80    # lower → reject colored objects more aggressively
CENTER_TOLERANCE_PX  = 25    # bigger → less wobble, but cuts corners
```

White line missed → lower `WHITE_VALUE_MIN` to 160 / 150.
Background detected as line → raise to 200 / 220.
Colored objects detected as line → lower `WHITE_SATURATION_MAX` to 40 / 50.

## Drive speed

```python
FORWARD_SPEED     = 30   # straight-line speed (0–100)
TURN_SPEED        = 45   # base speed inside steering corrections
SEARCH_TURN_SPEED = 22   # in-place rotation speed during SEARCH / OBSTACLE
```

Too fast → drop `FORWARD_SPEED` to 25. Too slow to make turns → raise
`TURN_SPEED`.

## Steering PID

```python
STEERING_PID_KP            = 0.30
STEERING_PID_KI            = 0.0
STEERING_PID_KD            = 0.05
STEERING_PID_OUTPUT_LIMIT  = 35
STEERING_PID_INTEGRAL_LIMIT= 200
```

Tune in this order: KI=KD=0, raise KP until it just barely holds the line.
Add KD to damp wobble. Add KI only if there's persistent off-center drift.

## Obstacle threshold

```python
OBSTACLE_DISTANCE_CM = 20.0   # ultrasonic ≤ this → state=OBSTACLE
```

Car stops too late → raise to 25–30. Twitches on every wall → lower to 12–15.

## Sweep search

```python
SEARCH_SWEEP_SEC        = 0.4   # duration of each sweep direction
SEARCH_INITIAL_STOP_SEC = 0.3   # brief stop on entry into SEARCH / OBSTACLE
SEARCH_TURN_SPEED       = 22
```

Wider arc → raise `SEARCH_SWEEP_SEC` to 0.6–0.8. Too aggressive on small
gaps → lower to 0.25.

## Motor direction inverts

```python
INVERT_FORWARD  = False
INVERT_STEERING = False
```

If forward goes back, flip `INVERT_FORWARD`. If left goes right, flip
`INVERT_STEERING`.

---

# CLI reference

```text
python -m raspbot.apps.line_follow [options]

Options:
  --camera {picamera2,usb}        Camera backend (default: picamera2)
  --camera-index N                USB camera index (default: 0)
  --debug                         Verbose per-frame state logging
  --dry-run                       Print motor commands; wheels don't move
  --no-sensors                    Skip ultrasonic + IR init (sensors not wired)

  --stream                        Serve MJPEG dashboard
  --stream-port PORT              (default: 8080)
  --stream-fps N                  Cap stream FPS (control loop unaffected)

  --fall-detection                Enable remote YOLO fall detection
  --fall-server URL               (default: config.FALL_SERVER_URL)
  --fall-camera-index N           (default: config.FALL_USB_CAMERA_INDEX)

  --voice                         Trigger LiveKit voice agent on fall
  --voice-api URL                 (default: config.VOICE_API_URL)
  --voice-robot-id ID             (default: config.VOICE_ROBOT_ID)
```

---

# Recommended first run order

Do not run the real car before camera, vision, sensor, and motor tests pass.

```bash
cd capstone-sensors.src
source .venv/bin/activate

python -m scripts.camera_test --camera picamera2
python -m scripts.vision_test --camera picamera2
python -m scripts.avoid_test
python -m scripts.motor_test
python -m raspbot.apps.line_follow --camera picamera2 --dry-run --debug
python -m raspbot.apps.line_follow --camera picamera2
python -m raspbot.apps.line_follow --camera picamera2 --stream
python -m raspbot.apps.line_follow --camera picamera2 --stream --fall-detection
python -m raspbot.apps.line_follow --camera picamera2 --stream --fall-detection --voice
```
