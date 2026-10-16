# 🐣 DevPet — Your code has a heartbeat

A real, runnable virtual pet whose health follows your computer and development activity. Built for the **Tracker and Tail-er** hackathon theme.

![Description](https://img.shields.io/badge/stack-Python%20%2B%20tail%20CLI-9aebc6)

## Features

- **Real CPU and RAM tracking** via `psutil`, sampled every 2 seconds.
- **Real-time tail integration:** events are written as JSON Lines and streamed to the pet engine by a live subprocess: GNU `tail -n +1 -F` when available, otherwise native Windows PowerShell `Get-Content -Tail -Wait`.
- **Interactive browser dashboard:** Byte changes mood, health, energy, stress and XP in near real time; CPU and RAM sparklines; event feed and terminal panel.
- **Safe demo buttons:** simulate common events without crashing apps or stressing your computer.
- **Real test/build integrations:** wrap test suites and programs and automatically log successes or failures.
- **Optional PID monitoring:** detect a watched process stopping. An unexpected exit alone is *not* labeled as a crash; a supervised command's nonzero exit is labeled `APP_CRASH`.
- **Persistent progression:** pet stats replay from the log on restart. No separate database required.
- **Zero frontend build tools:** just Python and `psutil`; uses GNU `tail` or Windows PowerShell (built into Windows).

## Requirements

- Python **3.9+** (3.11+ recommended)
- **Windows 10/11 (native, no Ubuntu/WSL)**, macOS, or Linux
- On Windows: built-in Windows PowerShell; GNU `tail.exe` from Git for Windows is optional
- `pip` to install `psutil`

## Get started — Windows (no Ubuntu!)

1. Install Python 3.9+ from <https://www.python.org/downloads/windows/> if it's not already installed; enable **Add python.exe to PATH** when offered.
2. Close and reopen your terminals after installing Python. Verify in PowerShell with `py -3 --version`.
3. Extract the project ZIP, open the extracted **devpet** folder, and **double-click `START_DEV_PET.bat`**. It creates `.venv`, installs `psutil`, launches DevPet, and opens the browser.
4. If you also want a live CLI terminal, **double-click `SHOW_LIVE_LOGS.bat`**. It uses the native Windows `Get-Content -Tail 15 -Wait` command.

That's it — **no Ubuntu, WSL, Docker, or Git Bash required**. If you see a Microsoft Store Python error, check **Settings > Apps > Advanced app settings > App execution aliases** and disable Python Store aliases; then reopen PowerShell. If `py -3 --version` works, the launcher uses it automatically.

**Manual PowerShell commands** (run in the folder containing `app.py`):

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py --open-browser
```

## Get started — macOS / Linux

Open a terminal inside this project folder:

```bash
python -m pip install -r requirements.txt
python app.py
```

Then open **http://127.0.0.1:8765** in your browser. The dashboard waits a couple of seconds for the first CPU/RAM samples. Press **Ctrl+C** in the terminal to stop.

> On Windows, `START_DEV_PET.bat` is the easiest method. The app automatically selects PowerShell when GNU `tail.exe` is unavailable.

## Demo for judges (1 minute)

1. Show the live CPU/RAM charts and log-following panel (GNU tail or PowerShell depending on your machine).
2. Click **CPU spike** — Byte becomes stressed and an event appears in the feed.
3. Click **App crash** — Byte gets sick. This **simulates an event** and doesn't actually crash anything.
4. Click **Tests pass** and **Successful build** — Byte recovers, gains XP, and changes mood. Do it repeatedly to level up.
5. On Windows, double-click `SHOW_LIVE_LOGS.bat` to show native CLI streaming (`Get-Content -Tail 15 -Wait`). On macOS/Linux, show `tail -f logs/events.log`.

## Record real development events

From a **second terminal**, with DevPet running:

```bash
# A passing test command (replace the example command with your tests)
python devpet_cli.py tests -- python -c "assert 2 + 2 == 4"

# Or run this project's real test suite (after installing pytest)
python devpet_cli.py tests -- python -m pytest -q

# A program whose nonzero exit code is treated as a failed/crashed app
python devpet_cli.py run -- python -c "raise RuntimeError('demo crash')"

# Send your own events from a script or Git hook
python devpet_cli.py emit GIT_COMMIT "Fixed login bug"
python devpet_cli.py emit BUILD_SUCCESS "Deployment succeeded"
```

The log writer is a separate process in those commands. The running app sees new events **through the `tail` subprocess** — it does not read its own in-memory events directly.

### Monitor a real running process

Find a PID (use Task Manager on Windows or `pgrep -f myserver.py` on Linux/macOS) and start DevPet with:

```bash
python app.py --watch-pid 12345
```

DevPet reports `APP_STOPPED` if that process is later gone. It cannot determine whether the stop was intentional from PID disappearance alone.

### Custom port or log

```bash
python app.py --port 9000 --log my-devpet-events.log
python devpet_cli.py --log my-devpet-events.log emit TEST_PASSED "All tests passed"
```

By default DevPet binds to **127.0.0.1** (not public interfaces). Keep it local; it has no account login or network authentication.

## How `tail` fits in (and why it's not just a gimmick)

```text
Real CPU/RAM or tests/builds or demo actions
         | write_event() appends JSON lines
         v
   logs/events.log
         |
         | GNU tail -n +1 -F (macOS/Linux/Git for Windows)
         | OR Windows Get-Content -Tail -Wait (PowerShell)
         | both run as actual OS subprocesses
         v
    Python log-reader thread
         |
         | parses streamed JSON events
         v
    PetEngine (stats, mood, XP)
         |
         | GET /api/state (every second)
         v
    Browser dashboard / animated SVG pet
```

- GNU `tail -n +1` starts at the first line so the event log can restore progress; `-F` streams new lines and handles log rotation.
- Windows PowerShell `Get-Content -Tail 2147483647 -Wait` starts with existing lines and streams new ones; unlike GNU `tail -F`, PowerShell does **not reliably handle renamed/rotated logs**.
- Neither command monitors CPU or files itself; it streams log lines written by a collector.
- **Strict literal `tail` requirement?** Optionally install Git for Windows to get GNU `tail.exe` without Ubuntu; DevPet detects the executable automatically.
- CPU and RAM **measurements** don't affect Byte every two seconds. Only high-threshold transitions write game-effect events, preventing runaway pet damage.

### Byte's rules

| Event | Game effect |
| --- | --- |
| `CPU_HIGH` | -5 health, -8 energy, +18 stress |
| `RAM_HIGH` | -5 health, -10 energy, +15 stress |
| `APP_CRASH` | -25 health, -12 energy, +30 stress |
| `TEST_FAILED` | -12 health, -6 energy, +16 stress |
| `TEST_PASSED` | +8 health, +10 energy, -10 stress, +25 XP |
| `BUILD_SUCCESS` | +12 health, +10 energy, -12 stress, +30 XP |
| `GIT_COMMIT` | +4 health, +5 energy, -6 stress, +15 XP |
| `SYSTEM_RECOVERED` | +8 health, +12 energy, -18 stress |

Every 100 XP = one level up. Stats stay between 0 and 100.

## Run automated tests

```bash
python -m pip install pytest
python -m pytest -q
```

Tests cover game rules, event log format, CLI commands, the **real GNU `tail` subprocess** (including rotation on Linux), Windows command-selection logic, and HTTP endpoints. Test suite execution in this environment is on Linux; native PowerShell operation should be checked on your Windows PC.

## Project layout

```text
app.py               HTTP dashboard server and demo event API
runtime.py           CPU/RAM monitor + GNU tail / PowerShell subprocess and parser
pet_engine.py        Pet mood, stats, XP, deterministic replay
event_log.py         Append-only JSONL event writer
devpet_cli.py        Real tests/builds/external event integration
static/index.html    Dashboard structure + SVG pet
static/style.css     Visual design and pet animations
static/main.js       Live rendering + demo controls
tests/               Automated tests
START_DEV_PET.bat     Native Windows setup and launch (double-click)
SHOW_LIVE_LOGS.bat    Native Windows tail-style streaming (double-click)
README_WINDOWS_FIRST.txt  Short Windows quick-start
logs/events.log      Created automatically, stores activity and progress
```

## Reset the pet

Stop DevPet with Ctrl+C, then delete `logs/events.log`, and restart. This will reset Byte to its initial state. Do not delete the log while the app is running.

## Notes & limitations

- High CPU means **90%+** and high RAM means **90%+**; the warning clears at **75% or lower** (hysteresis to avoid repeated alerts).
- CPU/RAM polling is every two seconds. the log-following subprocess and browser polling add some latency; events are **near real time**, not instantaneous.
- No secret collection, keystroke tracking, or network monitoring.
- All app content is served from local static assets. Google Fonts are optional and fall back to system fonts when offline.
- The dashboard is meant for a **single local hackathon demo**, not public internet deployment.
