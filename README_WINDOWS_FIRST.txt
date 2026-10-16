DevPet on WINDOWS (no Ubuntu, no WSL)
====================================

1. Install Python 3.9 or newer for Windows from:
   https://www.python.org/downloads/windows/
   During installation, enable "Add python.exe to PATH" if offered.
   (The Windows Python launcher "py" works too.)
2. Close and reopen any Command Prompt/PowerShell/VS Code terminals.
3. Unzip this folder anywhere, e.g. your Downloads directory.
4. Double-click START_DEV_PET.bat INSIDE the devpet folder.
   It will create a virtual environment, install dependencies, launch the
   dashboard and open your browser at http://127.0.0.1:8765
5. To see live logs in a second window, double-click SHOW_LIVE_LOGS.bat.
   Press Ctrl+C to stop the log window; press Ctrl+C in the server window
   to stop DevPet.

If Python still shows the Microsoft Store error:
 - Search Windows for "App execution aliases" and disable App Installer
   aliases for python.exe and python3.exe.
 - Check `py -3 --version` in a NEW terminal, not the old one.

What about the "tail" hackathon requirement?
 - On Windows, the project detects GNU `tail.exe` if present (including
   the copy that comes with Git for Windows).
 - Otherwise it uses Windows PowerShell's built-in equivalent command:
     Get-Content -LiteralPath .\logs\events.log -Tail 15 -Wait
 - The app still uses a real shell subprocess to stream appended log
   entries into its pet game logic, not an in-memory simulation.
 - If judges strictly demand the literal `tail` command, install Git
   for Windows (Ubuntu/WSL are NOT required), then restart DevPet;
   the app will use Git's GNU tail.exe automatically if found.
 - PowerShell Get-Content -Wait does not reliably follow renamed/rotated
   logs, unlike GNU tail -F. For a hackathon demo this is usually fine.

Manual start in PowerShell:
  py -3 -m venv .venv
  .\.venv\Scripts\python.exe -m pip install -r requirements.txt
  .\.venv\Scripts\python.exe app.py --open-browser

Go to README.md for details on tests, demo events and API.
