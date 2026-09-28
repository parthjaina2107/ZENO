# 🎙️ ZENO — Secure Voice Automation & Remote Control

> **ZENO**: Control your entire computer via voice commands—either locally using your microphone or remotely from your smartphone—always protected by explicit permission gating before any action executes.

---

## 🌟 Key Features

1. **Safety & Permission System**:
   - Every action requires user confirmation before execution.
   - **Low Risk**: Single confirmation ("Open Chrome? Say YES").
   - **Medium Risk**: Detailed confirmation (File manipulation, typing text).
   - **High Risk**: Double confirmation (Deleting files, shutting down, terminal commands).
   - Detailed audit log kept in `audit_log.jsonl`.

2. **Dual-Mode Operation**:
   - **Local Mode**: Listens via microphone, offline Speech-to-Text, and offline Text-to-Speech (pyttsx3). Falls back to terminal text input if no microphone is plugged in.
   - **Remote Mobile Control**: Modern web app accessible from any smartphone browser with Web Speech API for voice input and browser speech output.
   - **Simultaneous Operation**: Local and remote control can run at the same time.

3. **AI Brain (Gemini + Offline Fallback)**:
   - Powered by Google Gemini 2.5 (`google-genai` SDK) to understand complex natural language instructions.
   - Built-in offline rule/keyword parser ensures common system queries work even when offline or without an API key.

4. **Extensive System Automation**:
   - **Applications**: Open and close software safely, list active apps, process termination safeguards.
   - **Browser**: Open URLs, search Google.
   - **System Telemetry**: Battery level & charging status, CPU usage, RAM utilization, disk space, IP address, and current time.
   - **Hardware Control**: Volume level & muting, desktop screenshots (previewed in real-time on mobile).
   - **File Operations**: Safe file creation, reading, copying, moving, and search. Deletions move files safely to the Windows Recycle Bin (`send2trash`). Path traversal outside user directories is blocked.
   - **Safe Command Execution**: Blocked dangerous commands policy (`format`, `rm -rf`, `reg delete`, etc.) with 30s timeout protection.

5. **Remote Security & Tunneling**:
   - Public HTTPS tunneling powered by `pyngrok`.
   - Access token passphrase verification.
   - 24-hour cryptographic JWT session tokens.
   - Brute-force rate limiting (10 failed attempts triggers a 1-hour lockout).

---

## 🚀 Quick Start

### 1. Requirements & Prerequisites
- Windows 10/11
- Python 3.11+ (installed automatically in `.venv` via `uv`)

### 2. Configuration
Copy `.env.example` to `.env` and fill in your keys:
```bash
copy .env.example .env
```
Settings inside `.env`:
```env
GEMINI_API_KEY=your_gemini_api_key_here     # Get free at https://aistudio.google.com/
NGROK_AUTH_TOKEN=your_ngrok_token_here     # Get free at https://ngrok.com/
ACCESS_TOKEN=your_secret_passphrase        # Passphrase used to log in from phone
SERVER_PORT=8765
```
*(Note: If you don't have a Gemini API key or Ngrok token yet, the agent will still operate locally and over your local Wi-Fi network using the built-in fallback parser!)*

### 3. Running the Agent

Run both local voice listener and remote web server concurrently:
```bash
.venv\Scripts\python.exe main.py --mode all
```

Run only the remote web server (ideal when away from your PC):
```bash
.venv\Scripts\python.exe main.py --mode server
```

Run only local voice control (terminal mode):
```bash
.venv\Scripts\python.exe main.py --mode local
```

Calibrate microphone for background ambient noise:
```bash
.venv\Scripts\python.exe main.py --calibrate
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

All 18 automated test suites verify:
- Configuration validation and safety lists
- Task execution (SystemOps, FileOps, BrowserOps)
- NLU understanding and command sanitization
- Multi-tier permission management and audit trail
- FastAPI authentication, endpoints, and session verification
