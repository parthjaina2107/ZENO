# ZENO Reliability Implementation Plan

Work on a branch (`git checkout -b hardening`) and make one commit per numbered step. For each step, **write the failing test first, then the fix**. Every step is small enough to finish and verify before moving on.

**Total effort:** roughly 11 to 12 hours.
**Rule:** don't expose the ngrok tunnel until Stage C is done. Until then, use `--mode local` or Wi-Fi only.

---

## Phase 0: Setup (15 min)

- [x] **0.1** Create a Windows venv, run `pip install -r requirements.txt pytest pytest-asyncio httpx`, then run `pytest`. Baseline should be 29 passing.
- [x] **0.2** Add `tests/conftest.py` with fixtures for a temp `audit_log.jsonl`, a temp memory file, and a fake speaker/listener. Almost every test below needs these.

---

## Phase 1: Trust-breaking bugs (about 2 hours)

### 1.1 Yes/no parsing
*Files: `voice/listener.py`, `tests/test_listener.py`*

- [x] Pull the decision logic into a pure function `parse_confirmation(text) -> Optional[bool]`.
- [x] Tokenize with `re.findall(r"[a-z']+", text.lower())`. Check deny words first, then approve words, each by whole word, never by substring.
- [x] Remove `ha`, `right`, `please` and `correct` from the approve list, because they appear in ordinary sentences.
- [x] If both an approve and a deny word appear, or neither does, return `None` so the user is asked again.
- [x] **Tests:** "no thanks", "cancel that", "no that's wrong" → `False`; "yes", "go ahead" → `True`; "yes no" and "maybe" → `None`.

### 1.2 WebSocket deadlock
*Files: `server/app.py`, `tests/test_server.py`*

- [x] In the `/ws` loop, handle `type == "command"` with `asyncio.create_task(handle_command(...))` instead of `await`. The loop keeps reading, so `permission_response` messages arrive while an action waits.
- [x] Track tasks in a per-connection set, and cancel them in the `finally` block on disconnect.
- [x] Add one module-level `asyncio.Lock` (`EXEC_LOCK`) around the "request permission → execute" section, so two commands can't run at the same time.
- [x] **Test:** send "open notepad", approve, and assert a success message arrives in under 1 second rather than a timeout.

### 1.3 Secrets
*Files: `config.py`, `main.py`, `tests/test_config.py`*

- [x] Add `ensure_secrets()` in `config.py`. If `JWT_SECRET_KEY` or `ACCESS_TOKEN` is missing or a known default, generate it with `secrets.token_urlsafe(32)` and append it to `.env`.
- [x] Remove the hardcoded defaults from `Config`.
- [x] In `main.py`, stop printing the passphrase. Print "Passphrase is in .env" instead.
- [x] In `TunnelManager.start_tunnel()`, refuse to start if the token is still a default.
- [x] Add `JWT_SECRET_KEY` to `.env.example`.
- [x] **Tests:** a token forged with the old default secret is rejected, and `.env` is created with random values on first run.

### 1.4 NLU matching
*Files: `brain/nlu.py`, `tests/test_nlu.py`*

- [x] Replace every `any(w in lowered ...)` with a compiled regex using `\b` word boundaries.
- [x] Move the "open/launch/start X" branch above the system-info branches, so "open instagram" is never read as "ram".
- [x] Return `understood: False` for ambiguous input so it falls through to Gemini.
- [x] **Tests:** the six known misroutes must not produce the wrong action:
  - "open instagram" → not RAM usage
  - "open telegram" → not RAM usage
  - "update my resume" → not time
  - "skip this song" → not IP address
  - "open program files" → not RAM usage
  - "block my screen" → not lock workstation

---

## Phase 2: Enforceable safety (about 3 hours)

### 2.1 Risk table
*Files: `config.py`, `brain/planner.py`*

- [x] Add `ACTION_RISK = {"system_info": "low", "screenshot": "low", "open_app": "low", "type_text": "medium", "file_create": "medium", "run_command": "high", "file_delete": "high", "shutdown": "high", ...}`.
- [x] In `plan()`, compute `risk = max_risk(table[action_type], llm_risk)`. The LLM can raise risk but never lower it.
- [x] Reject unknown action types as `unhandled` instead of defaulting to medium.

### 2.2 Parameter validation
*File: `brain/planner.py`*

- [x] Add a pydantic model per action (for example `RunCommandParams(command: str)` and `VolumeParams(level: conint(ge=0, le=100))`).
- [x] Invalid parameters mean the action is rejected before the permission step.

### 2.3 Honest confirmations
*Files: `brain/planner.py`, `executor/permissions.py`*

- [x] Write `describe_action(action)` that builds the confirmation text from the real parameters, such as `Run command: "dir C:\Users"`.
- [x] Use it instead of the LLM's `confirmation_message` for medium and high risk.

### 2.4 Approval binding
*Files: `executor/permissions.py`, `server/app.py`*

- [x] Give each `PlannedAction` an `action_id`, a hash of its type and parameters.
- [x] The remote permission payload includes it, and execution only proceeds if the approved ID matches the action about to run.

### 2.5 `run_command` hardening
*File: `executor/system_ops.py`*

- [x] Use an allowlist of first tokens (`dir`, `ipconfig`, `whoami`, `ping`, and so on) and run with `shell=False`.
- [x] Anything else is rejected with a message.
- [x] Keep `BLOCKED_COMMANDS` as a second layer.

### 2.6 Server hardening
*Files: `server/auth.py`, `server/app.py`*

- [x] Key the lockout by client IP, using `X-Forwarded-For` only when the request comes from the ngrok proxy (behind ngrok every request otherwise looks like it comes from one address).
- [x] Restrict CORS to your own origin.
- [x] Send the JWT as the first WebSocket message after connect instead of a URL query parameter, because URLs end up in logs.
- [x] Put `/health` behind the JWT.

### 2.7 Kill switch
*Files: `brain/zeno_brain.py`, `server/app.py`, `main.py`, `server/templates/index.html`*

- [x] Handle "stop", "cancel everything" and "abort" before NLU. They cancel pending tasks and clear pending permission futures.
- [x] Add a red STOP button to `index.html` that sends `{"type": "abort"}`.

---

## Phase 3: Operational reliability (about 3 hours)

- [x] **3.1 TTS echo** (`executor/permissions.py`): replace `speaker.speak(...)` with `speak_sync(...)` before `listen_for_confirmation`, so the mic never hears the prompt.
- [x] **3.2 STT honesty** (`voice/listener.py`): either lazy-load Whisper when `WHISPER_MODEL` is set (`whisper.load_model(...)`), or change the README to say recognition uses Google's online service. Pick one, since it currently does neither.
- [x] **3.3 Gemini calls** (`brain/api_utils.py`, `config.py`):
  - Wrap calls in `asyncio.wait_for(..., timeout=15)`.
  - Request JSON output for NLU (`response_mime_type="application/json"`).
  - Change the default `GEMINI_MODEL` to a model you've confirmed exists, such as `gemini-2.5-flash`. Check your AI Studio model list, since `gemini-3.8-flash` is not a model I recognize.
- [x] **3.4 Atomic memory writes** (`brain/memory.py`): write to `zeno_memory.json.tmp`, then `os.replace`.
- [x] **3.5 Windows details** (`executor/system_ops.py`): use `Path.home().anchor` instead of `C:\` for disk usage, and `pycaw` for real volume control. Fall back to the current key presses if it isn't installed.
- [x] **3.6 Clipboard** (`executor/system_ops.py`): restore the old clipboard in a `finally` after pasting.

---

## Phase 4: Packaging and operations (about 2 hours)

- [x] Pin versions in `requirements.txt` (`pip freeze` from a working venv), and add `pywin32`, `pyaudio` and `pycaw`. Move `openai-whisper` to `requirements-optional.txt`.
- [x] Use `RotatingFileHandler` for `voiceagent.log`.
- [x] Log the result of each action (success, error) in `audit_log.jsonl` next to its approval.
- [x] Add `start_zeno.bat` and a Task Scheduler entry so it starts at login without a terminal.
- [x] Update the README so it matches reality: the test count, STT behavior, the model name, and that vision sends screenshots to Google.

---

## Phase 5: Tests and CI (about 1 hour)

- [x] Make sure every bug in Phases 1 and 2 has a regression test (the 1.x tests above already cover most).
- [x] Add `.github/workflows/test.yml` running `pytest` on `windows-latest` with `pyautogui`, `pyaudio` and `win32com` mocked in `conftest.py`.
- [x] Protect `main` so merges require passing CI.

---

## Order and checkpoints

| Stage | Steps | After this, you can... |
|---|---|---|
| **A** | Phase 0, 1.1–1.4 | Trust the permission gate and the login |
| **B** | 2.1–2.3, 2.7 | Rely on risk levels and confirmations, with a stop button |
| **C** | 2.4–2.6, Phase 3 | Expose it over ngrok with reasonable confidence |
| **D** | Phases 4–5 | Run it unattended, with regressions caught |

If you're short on time: finish Stage A (about an hour or two), then the risk table (2.1) and the secrets check (1.3). After that ZENO is safe enough for daily local use, and the rest improves polish and robustness.
