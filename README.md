# 🎙️ ZENO — Secure Voice Automation & Remote Control

> **ZENO**: Control your entire computer via voice commands—either locally using your microphone or remotely from your smartphone—always protected by explicit permission gating before any action executes.

---

## 🌟 Key Features

1. **Safety & Permission System**:
   - Every action requires user confirmation before execution based on an enforceable risk hierarchy.
   - **Low Risk**: Single confirmation ("Open Chrome? Say YES").
   - **Medium Risk**: Parameter-bound confirmations (File manipulation, typing text, volume adjustments).
   - **High Risk**: Double confirmation & explicit prompts (Deleting files, shutting down, terminal commands).
   - Tamper-proof action binding: Remote approvals cryptographically bind to exact action IDs.
   - Detailed audit log kept in `audit_log.jsonl` recording decisions, action IDs, and execution results.
   - Emergency Kill Switch: Say *"stop"*, *"abort"*, or press the red **STOP** button in the mobile UI to immediately cancel running tasks and clear pending permissions.

2. **Dual-Mode Operation**:
   - **Local Mode**: Listens via microphone with Google Speech Recognition by default, or offline local OpenAI Whisper (when `WHISPER_MODEL` is configured). Output spoken via pyttsx3 Text-to-Speech (with TTS echo cancellation before listening). Falls back to terminal text input if no microphone is plugged in.
   - **Remote Mobile Control**: Modern responsive web app accessible from any smartphone browser with Web Speech API for voice input, real-time WebSocket communication, and responsive approval buttons.
   - **Simultaneous Operation**: Local and remote control can run at the same time.

3. **ZENO Cognitive Brain (Conversational AI + Memory + Multimodal Vision)**:
   - **General Conversational Intelligence**: Ask general questions, request explanations, or chat naturally. ZENO responds with spoken answers powered by `gemini-2.5-flash` (via the official `google-genai` SDK) with strict 15s timeouts and JSON response formatting.
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

---

## 🚀 Quick Start

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
GEMINI_MODEL=gemini-2.5-flash
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

Run the automated test suite with pytest:
```bash
.venv\Scripts\python.exe -m pytest tests -v
```

All 67+ automated unit and integration tests across 11 test suites verify:
- Configuration validation, auto-generated secrets, and safety lists
- NLU tokenization, regex word boundaries, and zero false-positive routing
- Multi-tier permission management, action ID binding, and audit logging
- Task execution (SystemOps, FileOps, BrowserOps)
- Atomic memory storage and persistence
- WebSocket deadlock prevention, command parallelism, and connection cleanup
- Rate limiting, IP tracking, and JWT authentication
