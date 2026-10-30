# Windows setup guide

This guide covers the source-based development preview. There is no signed ZENO
installer yet. Follow these steps in PowerShell as your normal Windows user.
Administrator privileges are not required for the usual installation.

## 1. Prerequisites

- Windows 10 or 11, 64-bit. Python 3.11 x64 is the currently tested baseline;
  compatibility with newer Python versions is not guaranteed.
- [Python for Windows](https://www.python.org/downloads/windows/), including the
  Python launcher (`py`), and [Git for Windows](https://git-scm.com/download/win).
- A connected microphone and speakers/headphones for voice use.
- Internet for downloading dependencies and the local speech model. Gemini,
  connected mail and online voice features also need internet at runtime.
- Your own Gemini API key for reasoning and complex tasks. Basic literal commands
  can use the local fallback, and mail accounts are optional.

Confirm the tools are installed:

```powershell
git --version
py -3.11 --version
```

If a command is unavailable, finish installing the corresponding tool and reopen
PowerShell. Use a folder you can write to; the source preview currently stores
some runtime files next to its source.

## 2. Download and install

```powershell
git clone https://github.com/parthjaina2107/ZENO.git
Set-Location .\ZENO
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-desktop.txt -r requirements-speech.txt -r requirements-awareness.txt
```

These commands install the base application, desktop UI, CPU speech recognition,
soft online voice and optional awareness/account libraries. Installing an account
library does not authorize an inbox. No virtual-environment activation is needed,
so there is no PowerShell execution-policy change to make.

If you already use [uv](https://docs.astral.sh/uv/), the equivalents are
`uv venv --python 3.11` and
`uv pip install --python .venv/Scripts/python.exe -r requirements.txt -r requirements-desktop.txt -r requirements-speech.txt -r requirements-awareness.txt`.
Use either installation method in the same `.venv`.

For optional Windows accessibility tools, install `pywinauto`:

```powershell
.\.venv\Scripts\python.exe -m pip install "pywinauto>=0.6.8"
```

The separate `requirements-optional.txt` also installs the legacy openai-whisper
backend and its dependencies. It is not required for the default faster-whisper
setup above.

## 3. Configure your API key and preferences

Copy the example only if you do not already have a project `.env`:

```powershell
if (-not (Test-Path -LiteralPath .env)) { Copy-Item -LiteralPath .env.example -Destination .env }
notepad .env
```

Set `GEMINI_API_KEY` to your own key from [Google AI Studio](https://aistudio.google.com/).
Keep it in this local file. `GEMINI_MODEL` selects the model; choose a model your
account can access using the [official model reference](https://ai.google.dev/gemini-api/docs/models).
The example uses `gemini-3.8-flash`; access and quotas depend on the provider and
account. Changing models does not remove API limits or guarantee free usage.

The desktop does not need an ngrok token. Leave `NGROK_AUTH_TOKEN` empty unless
you deliberately configure a public tunnel. Remote authentication placeholders
are replaced with random secrets when the server initializes; keep those private.

Useful preferences in `.env`:

| Setting | Meaning |
| --- | --- |
| `TTS_BACKEND=edge` | Soft online neural voice, with installed Windows speech fallback |
| `TTS_BACKEND=sapi` | Installed Windows speech, without online neural TTS |
| `TTS_VOICE=en-IN-NeerjaNeural` | Default female neural voice |
| `STT_BACKEND=faster-whisper` | Local CPU transcription with an explicitly downloaded model |
| `STT_ALLOW_ONLINE_FALLBACK=false` | Disable Google audio fallback when local transcription is unavailable |
| `STT_LANGUAGE=` | Automatic language selection; set `en` or `hi` to constrain it |
| `AWARENESS_ENABLED=false` | Disable background notification, mail, project and system collection |

Process environment variables take precedence over the project `.env`. A saved
`%LOCALAPPDATA%\ZENO\.env` supplies fallback values when present; blank project
values can mask those fallbacks. Use the project `.env` as the main configuration
for a new source installation. Restart ZENO after changing it.

## 4. Prepare speech and check setup

```powershell
.\.venv\Scripts\python.exe main.py --setup-speech
.\.venv\Scripts\python.exe main.py --doctor
```

The first command downloads the configured speech model to the local ZENO data
directory. Initial download/loading can take time. Run it again if you change
`WHISPER_MODEL`. Normal listening does not download models automatically.

The doctor checks cached model loading and configuration without recording or
reading email. A configured API key or saved account sign-in is not a verified
live connection. Optional voice preview:

```powershell
.\.venv\Scripts\python.exe main.py --voice-preview
```

## 5. Start the desktop and choose your shortcut

```powershell
.\.venv\Scripts\python.exe main.py --desktop
```

After installation you can also double-click `Start-ZENO.cmd` to open the app
without a terminal.

1. Open **Keyboard shortcut**, click the shortcut field, press your combination
   and click **Save shortcut**. There is no preassigned shortcut.
2. Use a combination such as Ctrl+Shift+Y or a supported function key. Avoid
   keys used by other apps; NVIDIA may intercept Alt+Z combinations. Fn behavior
   depends on your laptop. Windows-key combinations and reserved F12 are rejected.
3. Open **Voice & microphone** and select an available input device. If Windows
   blocks it, review microphone access for desktop apps in Windows Settings.
4. Press your shortcut once. Wait for **Listening**, say **“what time is it”**,
   then pause naturally. There are 15 seconds to begin and 25 seconds per phrase.
   A small floating panel appears near the bottom of the screen containing your
   pointer, even when the settings window is hidden. It shows microphone activity,
   the recognized command after transcription, and progress without taking focus.
   It disappears four seconds after the request finishes.
   In **Voice & microphone**, choose the pause before sending: **Quick (0.6s)**,
   **Balanced (0.9s)** or **Relaxed (1.4s)**. Quick is the new default, including
   for existing settings files. Choose Relaxed if your phrases get cut short.
   A two-minute silence is not required; the selected short pause sends the request.
5. Press the **same shortcut while busy** to stop. During recording this discards
   the recording; it does not submit it. Remaining actions and spoken output stop.
6. If recognition is uncertain, review the editable draft and Send it, or retry.

You can also type a command. Try `open notepad` only after the time query works.
Deletion and shutdown/restart still need approval. Stopping does not undo
completed actions, and an already-started OS call may finish. See the
[desktop guide](desktop.md) for the exact cancellation behavior.

Closing the window keeps it in the tray while the tray is available. **Quit ZENO**
releases the shortcut and exits. Run one desktop instance at a time. Automatic
Windows startup is not enabled by these steps.

## 6. Optional email and work updates

The setup above does not connect Gmail or Outlook automatically. Follow the
[account and awareness guide](awareness.md) for Google Desktop OAuth JSON,
Microsoft client registration, notification access and supported commands.

```powershell
.\.venv\Scripts\python.exe main.py --connect gmail --credentials "C:\path\outside-repository\google-client.json"
.\.venv\Scripts\python.exe main.py --connect outlook
```

Run only the provider command you configured. Outlook requires `OUTLOOK_CLIENT_ID`.
Keep the terminal running through sign-in. If a Google localhost callback is
refused, rerun the connect command and use its newly opened browser page; an old
callback is not a standalone web service. Never paste OAuth tokens into issues.

`--briefing` checks live sources and may fetch private metadata; use it deliberately:

```powershell
.\.venv\Scripts\python.exe main.py --briefing
```

In desktop mode, connected sources collect while the engine runs and briefings are
available on request. The desktop currently does not announce background digests
automatically. Messaging coverage is limited to notifications Windows exposes.

## 7. Other operating modes

```powershell
# Local typed requests
.\.venv\Scripts\python.exe main.py --mode local --text
# Local continuous voice
.\.venv\Scripts\python.exe main.py --mode local --calibrate
# Optional local wake-word session
.\.venv\Scripts\python.exe main.py --mode local --calibrate --wake-word
```

For remote browser control, explicitly start `--mode server` (or `--mode all` for
both local voice and server). The current default server host is `0.0.0.0`, which
listens on all network interfaces. Set `SERVER_HOST=127.0.0.1` for this computer
only; LAN access needs an appropriate interface and firewall configuration.
Use the printed URL and your private `ACCESS_TOKEN`. The desktop mode itself does
not start this server. Public tunneling is optional and needs a real ngrok token.
Phone browser microphone access can depend on HTTPS and browser permissions.

The older `start_zeno.bat --background` and `scripts/register_task.bat` launch the
legacy local/server interface; they are not desktop startup installers. Do not run
the startup-registration script merely to configure a desktop shortcut.

## 8. Updating an existing installation

Quit ZENO first. In the project folder:

```powershell
git status --short
git pull --ff-only
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-desktop.txt -r requirements-speech.txt -r requirements-awareness.txt
.\.venv\Scripts\python.exe main.py --doctor
.\.venv\Scripts\python.exe main.py --desktop
```

If Git reports local changes or refuses the pull, preserve and resolve your edits
before continuing. Do not reset or overwrite them. Compare the updated
`.env.example` with your own `.env` and add new settings manually. Do not replace
your keys or tokens. Read [CHANGELOG.md](../CHANGELOG.md) for setup changes; model
changes require `--setup-speech` again. There is no automatic updater yet.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| `.venv` command not found | Run environment creation from the repository root |
| Desktop dependency missing | Install `requirements-desktop.txt` with the same `.venv` interpreter |
| Silent launcher failure | Start `main.py --desktop` from PowerShell to see diagnostics |
| Shortcut unavailable or inactive | Save a different combination; check overlays and that ZENO is running |
| Already running | Open the existing tray icon; quit it before restarting |
| No speech recognized | Check input, Windows permissions, cached model and noise; try typed input |
| Model not cached | Run `--setup-speech`; verify internet and writable data directory |
| Gemini authentication/quota/model error | Check key, accessible model and provider quota; retry a basic command |
| AI unavailable / Gemini 503 | Google is overloaded or unreachable. Wait and use Retry; changing the key does not fix a 503. Direct local commands such as `check battery` remain available. A connected dashboard indicates local connectivity, not provider availability. |
| Unexpected voice/data transmission | Check `TTS_BACKEND`, `STT_BACKEND` and online fallback before your next request |
| Mail unavailable | Check account setup/status and reconnect; a saved token may have expired |
| Long Stopping state | An in-flight worker is still draining; another task will not start concurrently |

See [support instructions](../SUPPORT.md) for a redacted bug report and
[privacy/storage details](privacy.md) before sharing diagnostics or removing data.

Reasoning requests use an 12-second per-attempt timeout and a 36-second overall
fallback budget. SDK retries are disabled for these calls; ZENO manages retries
and fallback models. The underlying SDK transport also receives the timeout so
abandoned calls cannot keep retrying indefinitely. Worker cleanup may extend
the final return beyond the application budget. Restart ZENO after upgrading;
no credentials, packages or environment changes are required.

## Glass web workspace

The web dashboard is served by the same FastAPI process as `/auth`, `/ws`, and
`/api/devices`; no separate frontend build or API URL is needed. Start it with
`.venv\Scripts\python.exe main.py --mode server`, then open
`http://127.0.0.1:8765` (or your configured `SERVER_PORT`). Your normal `.env`
configuration supplies provider keys; never copy them into frontend code.

After upgrading, restart ZENO and refresh the browser. Older sessions may need
one fresh sign-in to pair the browser. The UI creates a random browser device ID,
submits it with the access token, and sends the returned JWT as the first
WebSocket message. Revoked devices cannot submit further commands or approvals.

Agent task mode supports explicit offline sequences and bounded model planning.
Single command mode preserves the configured routine-action policy. Browser voice
input produces an editable draft: review it and press Run. Voice capture requires
a browser that supports SpeechRecognition and microphone access; typing remains
available. Browser preferences include spoken replies, recognition language, and
reduced motion. Reduced motion disables cursor lighting; touch input never enables it.

See [the UI verification notes](ui-redesign.md) and
[agent implementation notes](agent-task-upgrade.md). Local CLI and native desktop
retain their contextual verified-task workflows, which require Gemini for goal
planning. Do not run independent ZENO processes against the same desktop at once.


## Persistent desktop island and separate dashboard

`main.py --desktop` and `Start-ZENO.cmd` start the compact island. Hover opens its
quick-access panel, not the dashboard. Moving the pointer away collapses it after
550 ms, unless an approval needs your answer. Draft text is retained; running
work continues. Cursor lighting follows the pointer across the island controls.

Choose **Open workspace** on the island or **Open dashboard** in the tray to open the
full workspace in a separate resizable window. Closing it leaves the island
running. Both use the same desktop controller, without a web server or token.
Choose **Preferences** on the island or **Preferences** in the black dashboard
for microphone, shortcut, pause and spoken-reply settings. The old white desktop
settings window has been removed. Save settings on this page; the existing
desktop.json location and values are preserved. Restart desktop mode to load
this interface update; no new dependencies or migration are required.

After upgrading, quit ZENO and install the optional desktop requirements:

```powershell
uv pip install --python .venv/Scripts/python.exe -r requirements-desktop.txt
.\.venv\Scripts\python.exe main.py --desktop
```

PySide6-Essentials supplies the island. The separate desktop dashboard also needs
the pinned PySide6-Addons and PySide6-WebEngine packages. They are loaded only
when opening that dashboard; CLI/server installations do not require Qt. Keep
versions aligned with `requirements-desktop.txt`. No credentials or settings
migration is needed. Reduced motion in dashboard Preferences applies to both
interfaces for the session. Windows sign-in startup remains unchanged.
See [desktop controls](desktop.md).

## Notch lighting update

Restart desktop mode and refresh the browser to load the matte-black workspace
and compact voice panel. No new dependencies or configuration migration are
required. A screen-edge light and island rim appear only while the native audio
stream is open, after activation. They do not grant microphone access or replace
Windows permission indicators. An unavailable microphone never shows the active
light. Stop/stream closure clears it. Reduce motion in Preferences retains a
static microphone indicator while disabling pulses and sweeps. See the
[interface and microphone lifecycle](desktop.md#reactive-notch-interface).

## OriginKit-inspired island update

Restart desktop mode to load the redesigned native island. **Open workspace**
opens the existing dashboard separately; **Preferences** opens its settings page.
The island now includes local ribbon/cursor effects, icon tiles and a panel that
grows for the composer and approvals. **Minimize** or leaving the island returns
to the pill. The normal shortcut, voice settings and approval policy are retained.
No package install, browser server, credential or settings migration is required.
Icons and their license are bundled in `desktop/assets/icons/`. Keep that folder
with the desktop sources when copying a checkout. Reduced motion also controls
ribbon and button animation. See [island details](desktop.md#originkit-inspired-island).

## Native coding-workspace update

Install/sign in to a current Codex CLI; VS Code is detected separately. For PDF
instructions install `requirements-coding.txt` in the project environment. Restart
desktop mode, select **Coding task · Codex** and supply a full project folder.
Optional settings: CODING_CODEX_PATH, CODING_VSCODE_PATH, CODING_MODEL and
CODING_TIMEOUT_SECONDS (default 900). Existing OneDrive Desktop/Documents roots
are now permitted alongside local file roots; existing shortcut aliases remain
unchanged. No Gemini change, model training or settings migration is required.
Context consent and approved file proposals precede saving. Reports, provider
logs and backups persist in ZENO_DATA_DIR/coding_runs. Generated code and runtime
tests are not executed automatically. See [coding workspaces](coding-workspace.md).

## Companion conversation update

Restart ZENO and refresh the dashboard to get **Just talk** for conversation-only
text and native voice turns. Island/CLI requests can use `Chat:`. Existing Gemini
credentials/models and speech settings apply; no new packages, training dataset,
model download or account is required. Explicit `conversation style gentle` (also
balanced/playful/direct) saves a preference in the existing memory file.
`clear conversation` clears in-process dialogue context, not saved facts or UI/
provider copies. The new mode does not add background listening. See
[companion controls, provider data and limitations](companion.md). No settings
migration is required; general conversation still needs a working provider.

## Assistant experience update

Restart desktop mode and refresh browser pages. Dashboard Preferences now offers
Assistant personality: choose Focused, Warm or Balanced and Apply profile. The
choice persists in the existing memory file; Balanced is the default. The island's
Assistant/Just talk toggle controls its own text, Talk button and activation
shortcut for this session. Dashboard modes remain independent. Escape works while
the island has focus, stopping a request or collapsing idle UI. No new packages,
accounts, environment variables or voice models are needed. Existing speech and
approval settings are retained. See [assistant controls and preview](assistant-experience.md).
