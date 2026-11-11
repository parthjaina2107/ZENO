# Windows setup guide

## Windows installer

1. Use a 64-bit Intel or AMD PC running Windows 10 or 11. Connect to the internet
   and allow several GB of free disk space for Python, Qt and model downloads.
   Quit an existing instance of ZENO before installing or updating.
2. [Download ZENO-Setup-x64.exe](https://github.com/parthjaina2107/ZENO/raw/refs/heads/main/installers/ZENO-Setup-x64.exe).
   This preview is unsigned. To check the download, run
   `Get-FileHash "$HOME\Downloads\ZENO-Setup-x64.exe" -Algorithm SHA256` in
   PowerShell and compare the result with the [published SHA-256](../installers/ZENO-Setup-x64.exe.sha256).
   If your organization blocks unsigned apps, use its approved installation process.
3. Double-click the EXE. Local speech recognition is selected by default.
   Select **Install Ollama and download qwen3:4b** for local AI reasoning.
   That option uses Windows App Installer (winget) if Ollama is missing and
   downloads several additional GB. Leave speech unchecked for a text-only start.
4. Click **Install**. Keep the setup window open while it downloads the private
   Python runtime, verified packages and selected models. Choose **Open ZENO
   Desktop** on the last page. Later, open it from Start.
5. Hover over the island, open **Open workspace**, then choose **App access**.
   Enable the features you want. For example, enable **Microphone** for voice
   or **Local Ollama** for local AI. Account connections require your own sign-in.
   For a first check, enable **System information**, select **Single command**,
   type `check battery` and click **Run command**. A PC without a battery may
   report that the battery is unavailable.
6. If setup fails, read `%TEMP%\ZENO-setup.log`. Check network access to PyPI
   and GitHub, and to Hugging Face or Ollama for the selected models. Retry
   setup or deselect the failing model and add it later using the steps below.
   If the EXE itself cannot run, use the manual installation path.

The installer uses `%LOCALAPPDATA%\Programs\ZENO Desktop`. To update, quit
ZENO and run the newer installer. To uninstall, open **Settings → Apps → Installed
apps → ZENO Desktop → Uninstall**. The uninstaller removes its runtime, application
files and shortcuts. User-created files, settings and speech models in
`%LOCALAPPDATA%\ZENO` are retained, as are Ollama and its models. Review the
[data locations](privacy.md) before removing personal data.

For commands in this guide that use `.\.venv\Scripts\python.exe`, EXE users
can first run `Set-Location "$env:LOCALAPPDATA\Programs\ZENO Desktop"` in PowerShell.
The installer includes its own Python. For another supported Windows x64 PC,
download the EXE there and run setup under the intended user's Windows account.

File reads return a preview of up to 200 lines or 64 KiB. Ordinary file commands
block common credential files, hard-linked files, and tree operations containing
protected files or links. Close-app requests go to one visible window. If several
match, focus the desired window and retry. Respond to save prompts in the app.
Existing logs and task reports may retain private text from older versions;
see the [privacy guide](privacy.md) before sharing them.

## Manual installation

1. Install Git and Python 3.11 x64 using [Prerequisites](#1-prerequisites).
2. Open PowerShell and follow [Download and install](#2-download-and-install)
   to create a private environment and install dependencies.
3. Follow [Configure your API key and preferences](#3-configure-your-api-key-and-preferences)
   to create a local configuration and choose your AI runtime. For local speech,
   run `.\.venv\Scripts\python.exe main.py --setup-speech` from the ZENO folder.
4. From that folder run `.\Start-ZENO.cmd`. Open the workspace from the top
   island and choose your permissions under **App access**.

## Separate Aurora prototype

The independent music-lyrics prototype lives in `standalone/aurora`. Follow its
own setup guide and launcher; it has a separate
environment and does not use ZENO accounts, keys or services. Its optional Windows
media bridge supports optional LRCLIB lookup, local lyrics/preset storage, desktop
overlay and opt-in tray/startup operation. Spotify play/pause and a YouTube Music
sample with automatic lyrics were checked; full player smoke tests remain pending;
an unsigned local portable build is available. ZENO installation and upgrades do
not require Aurora dependencies. Aurora's guide documents its separate storage,
online metadata transmission and startup removal.
Aurora hosts desktop ambience below the icons in Explorer's wallpaper layer
(`--desktop` or **Show desktop ambience**), remembered between launches. Restart
Aurora after updating to remove the older canvas that covered icons. It runs while
Aurora is open and preserves your saved wallpaper/lock screen. Unknown shell layouts
leave ambience hidden; toggle it again after Explorer recreates its desktop.
`--player Spotify.exe` selects Spotify explicitly. New tracks fetch automatically;
temporary lookup failures retry with backoff. Search accepts matching title, lead
artist and duration across album releases without requiring version selection.
The reference-inspired Edge light appearance is selected once on upgrade: dark
centre, perimeter glow and floating lyrics. Restart Aurora to apply it; old styles
remain in the style selector. No dependency, account or wallpaper-setting changes.

For a source installation, follow these steps in PowerShell as your normal Windows user.
Administrator privileges are not required for the usual installation.

## 1. Prerequisites

- Windows 10 or 11, 64-bit. Python 3.11 x64 is the currently tested baseline;
  compatibility with newer Python versions is not guaranteed.
- [Python for Windows](https://www.python.org/downloads/windows/), including the
  Python launcher (`py`), and [Git for Windows](https://git-scm.com/download/win).
- A connected microphone and speakers/headphones for voice use.
- Internet for downloading dependencies and the local speech model. Gemini,
  connected mail and online voice features also need internet at runtime.
- Ollama with a downloaded model for local reasoning, or an optional confirmed
  Free-tier Gemini project. Basic literal commands
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
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-desktop.txt -r requirements-speech.txt -r requirements-awareness.txt -r requirements-coding.txt
```

These commands install the base application, desktop UI, CPU speech recognition,
soft online voice and optional awareness/account libraries. Installing an account
library does not authorize an inbox. No virtual-environment activation is needed,
so there is no PowerShell execution-policy change to make.

If you already use [uv](https://docs.astral.sh/uv/), the equivalents are
`uv venv --python 3.11` and
`uv pip install --python .venv/Scripts/python.exe -r requirements.txt -r requirements-desktop.txt -r requirements-speech.txt -r requirements-awareness.txt -r requirements-coding.txt`.
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

ZENO now defaults to **local AI**, with cloud calls disabled even if a Gemini key
is already saved. Install Ollama from its [Windows instructions](https://docs.ollama.com/windows),
then download the text model once:

```powershell
ollama pull qwen3:4b
```

ZENO looks for `%LOCALAPPDATA%\ZENO\ollama\ollama.exe` (portable), then the
standard `%LOCALAPPDATA%\Programs\Ollama` installation, then PATH. Desktop/CLI
startup launches an installed server hidden on `127.0.0.1:11434` with
`OLLAMA_NO_CLOUD=1` if that port is not already in use. It never downloads models
on startup. The server may remain running after ZENO closes; stop its process
when finished. Models normally live in `%USERPROFILE%\.ollama\models`; set
Ollama's own `OLLAMA_MODELS` only if you deliberately choose another location.
An already-running server is not reconfigured; cloud-backed model aliases are
rejected by the request adapter. No Windows login-startup entry is added by ZENO.

Set these values in your existing `.env`, preserving credentials:

```dotenv
LLM_MODE=local
GEMINI_FREE_TIER_CONFIRMED=false
LOCAL_LLM_ENABLED=true
OLLAMA_MODEL=qwen3:4b
OLLAMA_TIMEOUT_SECONDS=90
TTS_BACKEND=sapi
STT_BACKEND=faster-whisper
STT_ALLOW_ONLINE_FALLBACK=false
```

Install `requirements-speech.txt` and run `main.py --setup-speech` once for local
speech recognition (see the speech section below). SAPI uses installed Windows
voices. Existing `.env` speech settings retain precedence: change them explicitly
when upgrading if they currently select online speech. Text input works without
a microphone or cached speech model.

For optional free cloud reasoning, create/check your project in
[Google AI Studio](https://aistudio.google.com/): **billing must be disabled and
the project must be on Free tier**. A key cannot prove billing status. Only after
checking that, set `LLM_MODE=free-cloud-local`, `GEMINI_FREE_TIER_CONFIRMED=true`,
and `GEMINI_API_KEY` to that project's key. Leave confirmation false if unsure.
The default `GEMINI_MODEL=gemini-3.8-flash` and fallback Flash models have free-tier
standard inference listed in [Google pricing](https://ai.google.dev/gemini-api/docs/pricing)
as reviewed on 2026-10-31. Eligibility, quotas and pricing can change; confirmation
is a user assertion, not an automatic billing check or a guarantee of zero charges.
Do not enable billing. No paid model, hosted search/tool or cache option is routed.
On quota/auth failure ZENO immediately tries local AI; other cloud failures have
a bounded retry chain. Local inference has a separate 90-second default deadline.

Simple supported commands still use the local parser first. Chat, interpretation
and task planning can use the downloaded model; all actions retain parameter
validation and permission checks. Qwen3 4B handles text requests. To enable local screen interpretation, run
`ollama pull qwen3-vl:2b` with the installed Ollama runtime. If you installed the
portable runtime under `%LOCALAPPDATA%\ZENO\ollama`, use its `ollama.exe`.
Set `OLLAMA_VISION_MODEL` to select a different installed vision-capable model.
Start ZENO and ask “read my screen” or “explain the error on my screen”. ZENO
captures one primary-monitor image per request. Local mode sends the image to
the loopback Ollama service for inference. Cloud vision
requires the explicitly enabled free-cloud mode. Free-tier cloud requests can
send conversation context, requested file contents or explicitly requested screen
images to Google; its free-tier terms may allow product improvement use.

A 16 GB RAM / 4 GB GPU laptop is a reasonable starting target for the compact
model, but speed and memory headroom need local checks. No full-size model or
fine-tuning is required. To disable local inference, set `LOCAL_LLM_ENABLED=false`;
with cloud disabled, only the deterministic fallback remains.

Verify local text, structured routing and task planning without recording or
running actions:

```powershell
.venv\Scripts\python.exe scripts\local_ai_smoke.py
```

Restart ZENO after changing settings. Optional Codex coding workflows and
user-requested online integrations are separate from this reasoning router; local
mode does not make those integrations offline or change their billing terms.
External Codex execution now defaults off (`CODING_ALLOW_EXTERNAL=false`). Only
set it true after separately deciding to use that account/service; it is not
covered by the free Gemini restriction. Existing coding users must opt back in.

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
   The island stays fixed at the top center of your primary display. Click the listening pill for
   controls. Hover over the idle pill to see the transcript and progress.
   It returns to its compact size when you move away. An open draft or pending
   approval keeps the panel expanded.
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

Browser access is optional. Start the following command on the unlocked Windows PC.
The browser workspace listens on loopback, including on upgrades with an old
`SERVER_HOST=0.0.0.0` setting. The desktop shortcut and default CLI start locally.

```powershell
.venv\Scripts\python.exe main.py --mode server
```

Open the printed loopback URL on the PC. For a phone, configure your ngrok token
and append `--tunnel` to the command, then open the printed **HTTPS** URL.
A saved ngrok credential alone does not open a tunnel. Direct LAN HTTP is disabled.

1. Enter the host's private `ACCESS_TOKEN` and the one-use code displayed in
   its terminal within five minutes. Approve the Windows prompt on the PC.
2. The default grant accepts play, pause, next, previous and stop. Enable
   **Media and volume** in the desktop dashboard for playback to work.
3. To allow a broader command session, restart server mode with
   `--remote-control`. The PC owner reviews each incoming command, and also
   reviews actions that require permission. Sending a Gmail draft shows its recipient,
   subject and body for a separate PC approval. Remote prompts time out after 30 seconds.
4. Press Ctrl+C on the host to disconnect. The grant ends after 15 minutes,
   five minutes without a command, or detection of a locked desktop.
   Restart server mode for a fresh grant after expiry, denial or pairing another device.
   Existing browsers must pair again after each restart. A started OS operation may finish.

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

This update upgrades Pillow and replaces python-jose with PyJWT for HS256 remote
sessions. Update the virtual environment before starting ZENO. In an existing
ZENO-only virtual environment, remove the retired packages with
`.\.venv\Scripts\python.exe -m pip uninstall -y python-jose ecdsa`. For a uv-managed
environment use `uv pip uninstall --python .venv/Scripts/python.exe python-jose ecdsa`
after installing the updated requirements with uv. Keep your existing access token
and JWT signing key. Existing unexpired device-generation sessions remain valid.

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

After upgrading, restart server mode and refresh the browser. Each launch
requires new pairing, even for a remembered device. The browser sends its
device ID, passphrase and one-use code over the pairing form. The WebSocket
takes the session token in its first message. Keep the data directory writable
for the registry and its adjacent `paired_devices.lock`.

Terminal commands run a single allowlisted diagnostic. Use `run command hostname`
or `run command echo Hello ZENO` for a local check. Shell chains and redirection
are rejected. Use `route print`, `arp -a`, or `ipconfig /all` for read-only
network diagnostics. File creation and copying require a free destination name. Closing an app matches
its exact executable or known app name, such as `close Microsoft Edge`.

Agent task mode supports explicit offline sequences and bounded model planning.
For a multi-word folder name, answer the clarification with `call it Project Notes`.
A remote agent folder request still needs plan approval after that answer. An approval
must include both the request ID and action ID. Refresh older browser clients after
upgrading. Local spoken approvals accept an explicit answer such as `yes` or `go ahead`.
Single command mode preserves the configured routine-action policy. Browser voice
input produces an editable draft: review it and press Run. Voice capture requires
a browser that supports SpeechRecognition and microphone access; typing remains
available. Browser preferences include spoken replies, recognition language, and
reduced motion. Changes to the operating system motion preference apply while
the dashboard is open. The dashboard ribbons follow the cursor and shift accent
color every 16 seconds. Reduced motion freezes both the ribbons and the matching
button colors.

See [the UI verification notes](ui-redesign.md) and
[agent implementation notes](agent-task-upgrade.md). Local CLI and native desktop
retain their contextual verified-task workflows, which require configured local or cloud AI for goal
planning. Do not run independent ZENO processes against the same desktop at once.


## Persistent desktop island and separate dashboard

Launch ZENO with normal window visibility using `Start-ZENO.cmd` or the command
below; forcing the GUI process into Windows hidden-window mode can hide the
dashboard even when the island appears. If this happens, quit ZENO and relaunch
normally. **Open workspace** also restores an existing minimized dashboard.
Restart after updating to load this restoration fix; no installation or migration
is required. If dashboard construction fails, the island shows a message and
the application log records the error for diagnosis; the button can retry.

`main.py --desktop` and `Start-ZENO.cmd` start the compact island. Hover opens its
quick-access panel, not the dashboard. Moving the pointer away immediately starts
the closing animation. The panel stays open while you type or review an approval. On shorter
displays, scroll the panel to reach all controls. Drafts survive an explicit collapse. Cursor lighting follows the pointer across the island controls.

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
required. During actual capture, a wide, slim dark island shows **Listening** on
its left and animated cyan bars on its right. Screen-edge lighting is removed.
Click the listening island to reveal **Stop** and other controls; hovering does
not expand it during capture. Approvals still open automatically. Stop/stream
closure clears the listening view. Reduce motion keeps the indicator static.
The island does not grant microphone access or replace Windows indicators. See the
[interface and microphone lifecycle](desktop.md#reactive-notch-interface).

## OriginKit-inspired island update

The current [liquid-metal outer shell](island-21st.md) uses a black center and
moving chrome reflections across all island sizes. Quit ZENO from its tray menu
and reopen `Start-ZENO.cmd` to load it. **Reduce motion** keeps the metal static.
This changes only local native drawing; no shader/npm package, account, setting
or saved-data migration is required.

The island also adapts the supplied [GlowCard spotlight](island-21st.md): pointer
movement lights nearby edges and action tiles. Quit from the tray and restart
with `Start-ZENO.cmd` or `.\.venv\Scripts\python.exe main.py --desktop` to load it.
Dashboard **Reduce motion** disables this effect for the session. No dependency
installation, React build, account, configuration or data migration is needed.

The current [liquid-glass treatment](liquid-glass.md) also applies to the workspace,
settings, dialogs and audit page. Restart desktop mode and refresh open browser
pages after updating. Keep `server/static/liquid-glass.css` with the bundled UI;
the native dashboard embeds it locally. No React, Tailwind, npm installation,
new account, environment setting or saved-data migration is required.

The newer [21st.dev-inspired island](island-21st.md) supersedes the earlier
visual treatment below. Quit ZENO from the tray and restart with
`.\.venv\Scripts\python.exe main.py --desktop` (or `Start-ZENO.cmd`) to load it.
No dependency installation, account, environment or settings migration is needed.
The listening pill is now 360px wide, capped to the available screen width;
hover still opens idle controls, and clicking opens controls during capture.
Dashboard **Reduce motion** also disables orb drift and waveform motion.

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


## App access and quitting ZENO

Enable **Media and volume** to show the current Windows media session on the
island. Players that publish a timeline show elapsed and remaining time.
Live streams without a duration show playback status. ZENO's current task and
microphone take priority. Hover over the black music pill to expand the artwork,
timeline and playback controls. Previous, play/pause and next follow the player's
supported actions. Select the microphone icon to open ZENO's assistant controls.

Open the native dashboard and choose **App access** in the sidebar. Switch on the
accounts, installed applications and tools you want ZENO to use. New profiles
start with these switches off. For voice, enable **Microphone**. For local AI,
enable **Local Ollama**. For folder commands, enable **Files and folders**.
Gmail inbox and Gmail sending have separate switches and still require the
corresponding Google consent. Coding requires **Coding workspace**, **Files and
folders** and the existing external coding configuration. Web and CLI requests
respect the host's selections. Only the native dashboard can change them.

Settings are saved in `app-access.json` inside `ZENO_DATA_DIR`. Changes apply to
subsequent operations, including background polling. Turning off a feature leaves
its provider credentials in place. AI, Windows and OAuth configuration can
independently limit a feature. The switches control ZENO's built-in tools.
Enabling **Local Ollama** starts the installed runtime when local AI is configured.
ZENO checks **Google Gemini** access before each cloud request, including retries.
Restart a running CLI voice session if its microphone was off at launch.
If ZENO reports that it cannot load these settings, close it and move the damaged
`app-access.json` aside. Reopen ZENO and choose the tools to enable again.

**Exit** on the island and **Exit ZENO** in the dashboard header close the desktop
app, including its tray icon. During a task, ZENO requests cancellation and quits
after the worker finishes. Exit also shuts down the dashboard's embedded browser.
Closing only the dashboard window hides the workspace.
You can click **Type a request** during speech playback to interrupt a reply and
enter the next command.

Update the project requirements for Windows media controls. Pause and resume now
use the current media session's explicit pause and play operations. Stop remains
available during active CLI work even after a wake window expires.

## On-demand Gmail requests

Connect your Google account using the Gmail steps above, then restart ZENO to load
the current command handler. Ask `check my emails`, `show unread emails`,
`search my emails for invoice` or `emails from alice@example.com`. Say
`read email 1` after searching to read that result. Up to five matches are returned
per search and numbered reads fetch up to 6,000 text characters. The existing
`gmail.readonly` scope covers these reads. If Gmail reports an expired connection,
rerun `python main.py --connect gmail` and finish the new Google sign-in page.
Requests work through the brain's command handler even with background awareness
disabled.

To enable drafting and sending, run the following in the project environment and
approve both Gmail permissions on Google's page.

```powershell
.\.venv\Scripts\python.exe main.py --connect gmail --gmail-compose
```

Ask `write an email to alex@example.com about rescheduling our call` for AI assistance,
or dictate exact wording with `draft an email to alex@example.com subject Meeting body Can we meet Friday?`.
ZENO saves the draft to Gmail and displays the recipient, subject and body.
To send, say `send draft` followed by the six-digit code in that preview.
In the desktop app you can also click **Send reviewed draft** under the preview
after speech playback finishes. Dictating just a number brings back the preview.
The code is specific to the current draft and session. `Cancel send` clears
the pending confirmation and leaves the draft in Gmail.
See [Gmail details](awareness.md#direct-gmail-inbox-connection).

For a multi-turn message, start with `send a mail to my friend`, supply the address
when asked, and then dictate the body. You can also say `create a folder named
Parthz on desktop then send an email to alex@example.com`. The mail step starts
only after folder creation succeeds. Digit-by-digit send codes and single-recipient
addresses spoken with “at” and “dot” are supported. Review the displayed address
before sending.
