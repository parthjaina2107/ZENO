# 🎙️ ZENO — Secure Voice Automation & Remote Control

> **ZENO**: Control your computer via local voice commands or your smartphone, with confirmation for deletion, shutdown, and restart.

---

## 🌟 Key Features

1. **Safety & Permission System**:
   - Routine actions execute immediately: opening apps, browser commands, volume, typing, shortcuts, file creation/copy/move, and allowed utility commands.
   - Confirmation is required only for file deletion and system shutdown/restart. Lock and sleep run immediately.
   - Local deletion/shutdown/restart retain double confirmation with exact action parameters.
   - Configure `CONFIRMATION_ACTIONS` and `CONFIRMATION_POWER_MODES` in `config.py` to change this policy. Existing path restrictions and command allowlists still apply.
   - Tamper-proof action binding: Remote approvals cryptographically bind to exact action IDs.
   - Detailed audit log kept in `audit_log.jsonl` recording decisions, action IDs, and execution results.
   - Emergency Kill Switch: Say *"stop"*, *"abort"*, or press the red **STOP** button in the mobile UI to immediately cancel running tasks and clear pending permissions.

2. **Dual-Mode Operation**:
   - **Local Mode**: Listens via microphone with Google Speech Recognition by default, or offline local OpenAI Whisper (when `WHISPER_MODEL` is configured). Output spoken via pyttsx3 Text-to-Speech (with TTS echo cancellation before listening). Falls back to terminal text input if no microphone is plugged in.
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

### Goal-driven console tasks

Run `.venv\Scripts\python.exe main.py --mode local --text` for keyboard input. Prefix a goal with `task:`, for example:

```text
task: Open Notepad, create Documents/zeno-demo.txt with the text Hello ZENO, then read the file back.
```

The task runner requests one validated action at a time from Gemini, uses results to plan the next step, verifies saved file contents, and saves a JSON report under `task_reports/`. It stops after 12 steps, repeated actions, invalid actions, failed tools, or denied permissions. Routine steps run immediately; deletion/shutdown/restart keep confirmation.

This first task engine supports existing app/file/diagnostic operations and verified typing into Notepad after opening it. Notepad typing requires `pywinauto` from `requirements-optional.txt`; it focuses the actual editor, appends text, and reads it back before reporting success. It preserves existing outputs, and reports unverified outcomes instead of trusting the model's claim of success. App launches are checked against running process names. Browser navigation and volume changes do not yet have independent outcome verification. General task-mode keyboard/mouse automation, browser page reading, and arbitrary project test runners remain future work. Use Ctrl+C to interrupt a local task; the phone STOP control cancels remote tasks. An OS operation already started may finish.

Task mode requires Gemini. The default model is `gemini-3.8-flash`, with configurable `GEMINI_MODEL` in `.env`. The optional live check `.venv\Scripts\python.exe scripts\task_smoke.py` opens Notepad and creates a new scratch file.

### 1. Requirements & Prerequisites
- Windows 10/11
- Python 3.11+ (installed in `.venv` via `uv`)

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
*(Note: If `JWT_SECRET_KEY` or `ACCESS_TOKEN` is not specified, ZENO will generate cryptographically secure keys automatically on first startup).*

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

Run the automated test suite with pytest:
```bash
.venv\Scripts\python.exe -m pytest tests -v
```

All 140 automated unit and integration tests verify:
- Configuration validation, auto-generated secrets, and safety lists
- NLU tokenization, regex word boundaries, and zero false-positive routing
- Multi-tier permission management, action ID binding, and audit logging
- Task execution (SystemOps, FileOps, BrowserOps)
- Atomic memory storage and persistence
- WebSocket deadlock prevention, command parallelism, and connection cleanup
- Rate limiting, IP tracking, and JWT authentication
- Read-only inbox adapters, awareness isolation, reminders, and OAuth recovery
- Local speech recognition, silence filtering, and speech-service fallbacks
