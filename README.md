# 🎙️ ZENO — Secure Voice Automation & Remote Control

> **ZENO**: Control your computer via local voice commands or your smartphone, with confirmation for deletion, shutdown, and restart.

**Status: development preview.** Source installation is available today. A signed
installer, automatic updates and a commercial release are not available yet.
Licensing remains undecided.

Start with the **[complete Windows setup guide](docs/setup.md)**. It covers a clean
checkout, dependencies, API configuration, microphone setup, first use and updates.

| Documentation | Purpose |
| --- | --- |
| [Windows setup](docs/setup.md) | Install, configure, run, update and troubleshoot |
| [Desktop guide](docs/desktop.md) | Custom shortcut, microphone and cancellation |
| [Awareness and accounts](docs/awareness.md) | Work updates, Gmail/Outlook and voice |
| [Privacy overview](docs/privacy.md) | Data flows, storage and removal |
| [Launch readiness](docs/launch-readiness.md) | Remaining commercial release requirements |
| [Changelog](CHANGELOG.md) | Changes and setup implications |
| [Contributing](CONTRIBUTING.md) | Development and documentation requirements |
| [Security](SECURITY.md) / [Support](SUPPORT.md) | Report vulnerabilities or product issues |

---

## 🌟 Key Features

1. **Safety & Permission System**:
   - Routine actions execute immediately: opening apps, browser commands, volume, typing, shortcuts, file creation/copy/move, and allowed utility commands.
   - Confirmation is required only for file deletion and system shutdown/restart. Lock and sleep run immediately.
   - Local deletion/shutdown/restart retain double confirmation with exact action parameters.
   - Configure `CONFIRMATION_ACTIONS` and `CONFIRMATION_POWER_MODES` in `config.py` to change this policy. Existing path restrictions and command allowlists still apply.
   - Remote approvals bind to action IDs and the requesting paired device.
   - Detailed audit log kept in `audit_log.jsonl` recording decisions, action IDs, and execution results.
   - Stop controls cancel pending work. Desktop mode uses the same keyboard shortcut to start and stop. Completed actions are not undone; OS calls already started may finish.

2. **Dual-Mode Operation**:
   - **Desktop Mode**: Native Windows app with a customizable global start/stop shortcut, status display, typed fallback, microphone selection and system tray. Microphone capture stays off until activation.
   - **Local CLI Mode**: Uses cached faster-whisper recognition by default, with configurable Google online fallback. Soft neural voice has installed Windows speech fallback. The microphone pauses during replies by default; optional headphone barge-in is not acoustic echo cancellation.
   - **Remote Mobile Control**: Modern responsive web app accessible from any smartphone browser with Web Speech API for voice input, real-time WebSocket communication, and responsive approval buttons.
   - **Simultaneous Operation**: Local and remote control can run at the same time.

3. **ZENO Cognitive Brain (Conversational AI + Memory + Multimodal Vision)**:
   - **General Conversational Intelligence**: Ask general questions, request explanations, or chat naturally. ZENO responds using the configured Gemini model via the official `google-genai` SDK, with timeouts and model fallback.
   - **👁️ Multimodal Screen Vision**: Ask *"Look at my screen, what's wrong?"* or *"Explain what is open on my screen"*.
     > **Privacy Notice**: Screen vision captures a local display screenshot and transmits the image to Google's Gemini API for multimodal comprehension.
   - **💾 Short-Term Context**: Multi-turn conversational memory allows follow-ups without repeating context.
   - **🗃️ Persistent Long-Term Memory**: Teach ZENO facts (*"Remember that my project path is C:\Projects"*), recall them (*"What is my project path?"*), or forget them (*"Forget my project path"*). Uses atomic file replacement to prevent data corruption.
   - **Offline Local Fallback**: Fast regex-based rule parser with word boundary tokenization ensures common system queries work offline without an API key and prevents misroutes (e.g. "open instagram" is never confused for RAM usage).

4. **Extensive System Automation**:
   - **Applications**: Open and close software safely, list active apps, process termination safeguards.
   - **Browser**: Open URLs, search Google.
   - **System Telemetry**: Battery level & charging status, CPU usage, RAM utilization, disk space (auto-anchored to user home drive), IP address, and current time.
   - **Hardware Control**: Real audio endpoint volume control via `pycaw` (falling back to virtual keys), desktop screenshots (previewed in real-time on mobile).
   - **Input & Clipboard**: Unicode clipboard-based text typing with automatic restoration of previous clipboard contents.
   - **File Operations**: Safe file creation, reading, copying, moving, and search. Deletions move files safely to the Windows Recycle Bin (`send2trash`). Path traversal outside user directories is blocked.
   - **Safe Command Execution**: Whitelisted safe utility commands (`dir`, `ipconfig`, `whoami`, `ping`, etc.) executed with `shell=False` and 30s timeout protection, backed by dangerous command blacklist.

5. **Remote Security & Tunneling**:
   - Public HTTPS tunneling powered by `pyngrok` with automatic secret generation.
   - Header-based JWT authentication (`Authorization: Bearer <token>`) for WebSocket and REST endpoints.
   - Brute-force rate limiting with client IP tracking (10 failed attempts triggers a 1-hour lockout).
   - CORS origin isolation.
   - Paired-device sessions: each browser receives a stable device identity, sessions are checked against a local revocation registry, and permission responses are accepted only from the device that requested the action.

6. **Phase 1 Trust & Review UX**:
   - Multi-step commands execute in order without a blanket approval prompt. Deletion/shutdown/restart steps still require their own confirmation.
   - A protected local audit dashboard is available at `/audit` after mobile sign-in, backed by `/api/audit`.
   - Ask “inspect the focused window” to report the active window and—when optional `pywinauto` is installed—discover named accessibility controls for future semantic automation.

---

## 🚀 Quick Start

### Windows desktop: press to talk

Install the optional native interface and launch it:

```powershell
uv pip install --python .venv/Scripts/python.exe -r requirements-desktop.txt
.\.venv\Scripts\python.exe main.py --desktop
```

Or double-click `Start-ZENO.cmd` after installing dependencies. The minimal,
Apple Settings-inspired app includes **Assistant**, **Keyboard shortcut**,
**Voice & microphone**, and **About & privacy** pages.

Choose your own shortcut in Settings: press it once to listen, speak and pause
to send, then press **the same shortcut while busy to stop**. The microphone is
closed until activation. Cancellation prevents remaining steps and interrupts
speech; an OS action already started may finish, and completed actions are not
undone. There is no automatic startup or remote-control server in desktop mode.
Closing the window keeps the app in the system tray; use **Quit ZENO** to exit.

New installation? Follow the [complete Windows setup](docs/setup.md) first; the
commands above assume the project environment and base dependencies already exist.
See [desktop controls and cancellation details](docs/desktop.md).

### Goal-driven console tasks

Run `.venv\Scripts\python.exe main.py --mode local --text` for keyboard input. Prefix a goal with `task:`, for example:

```text
task: Open Notepad, create Documents/zeno-demo.txt with the text Hello ZENO, then read the file back.
```

The task runner requests one validated action at a time from Gemini, uses results to plan the next step, verifies saved file contents, and saves a JSON report under `task_reports/`. It stops after 12 steps, repeated actions, invalid actions, failed tools, or denied permissions. Routine steps run immediately; deletion/shutdown/restart keep confirmation.

This first task engine supports existing app/file/diagnostic operations and verified typing into Notepad after opening it. Notepad typing requires `pywinauto` from `requirements-optional.txt`; it focuses the actual editor, appends text, and reads it back before reporting success. It preserves existing outputs, and reports unverified outcomes instead of trusting the model's claim of success. App launches are checked against running process names. Browser navigation and volume changes do not yet have independent outcome verification. General task-mode keyboard/mouse automation, browser page reading, and arbitrary project test runners remain future work. Use Ctrl+C to interrupt a local task; the phone STOP control cancels remote tasks. An OS operation already started may finish.

Task mode requires Gemini. The default model is `gemini-3.8-flash`, with configurable `GEMINI_MODEL` in `.env`; select a model your account can access. The optional live check `.venv\Scripts\python.exe scripts\task_smoke.py` opens Notepad and creates a new scratch file.

### 1. Requirements & Prerequisites
- Windows 10/11
- Python 3.11 x64 (currently tested baseline; see the setup guide)

### 2. Configuration
Copy `.env.example` to `.env` and fill in your keys:
```bash
copy .env.example .env
```
Settings inside `.env`:
```env
GEMINI_API_KEY=your_gemini_api_key_here     # Get free at https://aistudio.google.com/
GEMINI_MODEL=gemini-3.8-flash
NGROK_AUTH_TOKEN=your_ngrok_token_here     # Get free at https://ngrok.com/
ACCESS_TOKEN=your_secret_passphrase        # Passphrase used to log in from phone
SERVER_PORT=8765
```
*(The remote server initializes missing/default authentication secrets with random values. Keep your local `.env` private. Desktop-only use does not need an ngrok token.)*

### 3. Running the Agent

Run both local voice listener and remote web server concurrently:
```bash
start_zeno.bat
```
Or directly:
```bash
.venv\Scripts\python.exe main.py --mode all
```

Run in the background without a terminal window:
```bash
start_zeno.bat --background
```

Run only the remote web server:
```bash
.venv\Scripts\python.exe main.py --mode server
```

Run only local voice control:
```bash
.venv\Scripts\python.exe main.py --mode local
```

### 4. Windows Startup at Login (Optional)
To start ZENO automatically when you log into Windows (running silently in the background):

This legacy script starts the local/server interface, not the press-to-talk desktop app.
It is optional and is not part of desktop setup.
```bash
scripts\register_task.bat
```
To remove it from startup:
```bash
scripts\unregister_task.bat
```

---

## 📱 Connecting from your Phone

1. Start the agent with `--mode all` or `--mode server`.
2. The agent will display your connection links:
   - **Local Wi-Fi URL**: `http://<your-laptop-ip>:8765`
   - **Public Ngrok URL**: `https://<random-id>.ngrok-free.app` (if `NGROK_AUTH_TOKEN` is set)
3. Open the URL in Safari, Chrome, or any mobile browser.
4. Enter your secret `ACCESS_TOKEN` passphrase.
5. Tap and hold the **🎤 Hold to Speak** button, speak your command, and approve or deny any planned actions with one tap!

---

## 🧪 Testing

### Proactive updates and voice

ZENO now supports grouped Windows notification briefings, Git project status, system health
alerts, watched-process exit notices, and persistent reminders while running. Say **"Brief me"**,
**"Work status"**, **"Connection status"**, or **"Focus mode"**. A softer female neural voice
has a local Windows fallback. Optional Gmail/Outlook inbox connections require your own OAuth
sign-in; WhatsApp, Telegram and Discord coverage comes from available Windows notifications.

See [setup, commands, account access and limitations](docs/awareness.md). Install optional
dependencies with `uv pip install --python .venv\Scripts\python.exe -r requirements-awareness.txt`.

### Conversation and spoken feedback

ZENO gives one brief spoken outcome per request. Execution steps, character counts,
verification details and diagnostic errors remain in the console and task reports.
Questions about battery, time and other observations still get an informative answer.
Screen questions are interpreted rather than transcribed unless you ask for a readout.

With a working Gemini connection, requests beyond simple literal commands are interpreted
using recent conversation and actual execution outcomes. You do not need to say `task:`.
For example, say "Write a short poem about rain in Notepad". Missing details can trigger
a clarification question; answer it naturally. "Why does my laptop restart?" is a question,
not a restart command. Simple commands such as "Open Notepad" stay local and fast.

Context lasts for the current process; saved personal facts persist. Task planning still
uses the existing bounded tools: this does not add arbitrary browser interaction or
general GUI control. If reasoning is unavailable, complex requests stop with an explanation.

### Optional wake-word conversations

Run `python main.py --mode local --calibrate --wake-word`, then say “Hey ZENO”.
Follow-ups stay active for 30 seconds. Local speech diagnostics ask you to confirm
uncertain transcripts before execution. Headphone-only speech interruption is optional
(`VOICE_BARGE_IN=true`); it does not cancel running tasks. See
[conversation setup, privacy and limitations](docs/conversation.md).

Run the automated test suite with pytest:
```bash
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe scripts\check_docs.py
.venv\Scripts\python.exe -m pytest tests -v
```

The automated unit and integration tests verify:
- Configuration validation, auto-generated secrets, and safety lists
- NLU tokenization, regex word boundaries, and zero false-positive routing
- Multi-tier permission management, action ID binding, and audit logging
- Task execution (SystemOps, FileOps, BrowserOps)
- Atomic memory storage and persistence
- WebSocket deadlock prevention, command parallelism, and connection cleanup
- Rate limiting, IP tracking, and JWT authentication
- Read-only inbox adapters, awareness isolation, reminders, and OAuth recovery
- Local speech recognition, silence filtering, and speech-service fallbacks
