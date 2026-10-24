# DevPet

DevPet is a system monitor with a virtual pet called Byte. It tracks what is happening on your computer and turns certain events into changes in Byte's mood, health and XP.

I made it for the **Tracker & Tail-er hackathon**. I wanted to build something that used the `tail` command for a real purpose, rather than just displaying a log file in a terminal.

## DevPet Overview


<p align="center">
  <img src="https://github.com/user-attachments/assets/972719ec-8e91-42b2-a537-81e004baf6e7" width="800" alt="DevPet dashboard during normal system activity">
</p>

<p align="center">
  <strong>Figure 1: System Monitoring Under Normal Conditions</strong><br>
  <sub>DevPet displaying live system performance metrics and the virtual pet's status during normal computer activity.</sub>
</p>

<br>

<p align="center">
  <img src="https://github.com/user-attachments/assets/fff6c89f-0f33-47ae-9cf3-5d8391b4ca62" width="800" alt="DevPet watchlist, recent activity and demo events">
</p>

<p align="center">
  <strong>Figure 2: Watchlist, Recent Activity and Demo Events</strong><br>
  <sub>The watchlist and activity feed provide visibility into monitored resources and recorded events, alongside controls for testing simulated scenarios.</sub>
</p>

<br>

<p align="center">
  <img src="https://github.com/user-attachments/assets/3162d9f9-8d18-4526-a07a-2f76ed432de1" width="800" alt="DevPet dashboard under increased system load">
</p>

<p align="center">
  <strong>Figure 3: System Monitoring Under Load</strong><br>
  <sub>DevPet displaying changes in system resource usage under increased load, demonstrating how live monitoring affects the dashboard and virtual pet.</sub>
</p>






## Features

- **System monitoring:** CPU, memory, disk usage and network upload/download rates, sampled every 2 seconds. The dashboard shows the last 60 CPU and memory readings.
- **Process tracking:** Watch an application by name or PID and see when it starts or stops, plus its approximate memory usage.
- **Folder tracking:** Detect added, modified and deleted files in a selected folder.
- **Log monitoring:** Follow a text log file and pick up new warning and error messages.
- **Alerts:** Keep track of issues, acknowledge them, and see when CPU, memory or a watched process returns to normal.
- **Virtual pet:** Byte reacts to events and earns XP from successful tests/builds, file activity and recoveries. Progress is saved locally.

There are also a few optional demo buttons to show how Byte reacts. These are labelled as simulations and don't give XP.

## How it works

```text
CPU / memory / processes / files / app logs
                     |
               Python watchers
                     |
          data/events.log (JSONL)
                     |
          tail -F / PowerShell
                     |
                Event handler
                  /       \
             Alerts      Byte
                  \       /
              Local dashboard
```

The monitoring code writes each event as a JSON object on a new line in `data/events.log`. A log-following subprocess reads newly added lines, and the event handler updates alerts, recent activity and Byte's state. The browser gets the latest state from the local server every second.

For example, if a watched application log gets a new `ERROR` line, DevPet records a `LOG_ERROR` event, shows an alert and makes Byte worried.

## Design choices

I kept the stack small because this was a hackathon project:

- **Python + `psutil`:** `psutil` provides the system and process readings without having to write separate Windows-specific commands for every metric.
- **JSONL + `tail`:** One event per line is easy to inspect and debug. It also separates the code collecting events from the code reacting to them. DevPet uses GNU `tail` when available, or PowerShell's log-following command on Windows.
- **HTML, CSS and vanilla JavaScript:** A simple interface felt more appropriate than setting up a frontend framework. The backend uses Python's built-in HTTP server, so `psutil` is the only package dependency.
- **Polling:** System readings are taken every 2 seconds and the browser checks for updates every second. WebSockets would be faster for some uses, but polling was simpler and enough for this MVP.
- **Alert handling:** CPU and memory alerts start at 90% and recover below 75%, avoiding constant alerts around one threshold. Repeated log warnings/errors are also rate-limited.
- **Local storage:** Byte's progress, selected watches and alerts are saved to `data/save.json`. I didn't need a database for a single-user local app.

## Running on Windows

Requires **Python 3.10+**. No Ubuntu or WSL is needed.

1. Download or clone the repository.
2. Double-click `START_DEV_PET.bat`. It creates a virtual environment, installs `psutil` and starts the app.
3. Open **http://127.0.0.1:8765** in a browser.
4. Keep the terminal open while using DevPet. Press **Ctrl+C** to stop it.

Or run it manually in PowerShell:

```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe app.py
```

`SHOW_LIVE_LOGS.bat` lets you view the event stream separately in a terminal.

## Trying it out

**Applications:** Add `notepad.exe` as a process watch, then open and close Notepad. Start/stop events appear in the activity feed.

**Files:** Watch a test folder and add, edit or delete a text file.

**Logs:** Run the following in PowerShell:

```powershell
Set-Content "$env:TEMP\devpet-demo.log" "INFO application started"
```

Add that file's full path as a **Log file** watch, then append an error:

```powershell
Add-Content "$env:TEMP\devpet-demo.log" "ERROR connection failed"
```

DevPet should pick up the new line and update the alert list and Byte's mood.

## Project structure

```text
app.py              Local server and API
monitor.py          System metrics, watchers, event handling and pet state
log_reader.py       Reads and classifies new log lines
devpet_cli.py       Runs test/build commands and records the result
static/             Dashboard HTML, CSS and JavaScript
tests/              Automated tests
*.bat               Windows launcher and utilities
```

## Testing

Double-click `RUN_TESTS.bat` or run:

```powershell
py -3 -m unittest discover -s tests -v
```

The project passed **31 automated tests in the development environment**, covering monitoring, log processing, alerts, saved state and API behaviour. Run the tests locally as well before demonstrating the app.

## Limitations

This is a hackathon MVP, not a replacement for Task Manager or a production monitoring service. Folder changes are detected through periodic metadata checks, so quick changes between scans may be missed. Process termination doesn't necessarily mean a crash, and the log reader uses keyword matching rather than understanding every log format.

Everything runs locally on `127.0.0.1`. Avoid monitoring logs with personal information or secrets.
