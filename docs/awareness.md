# Proactive updates and a calmer voice

ZENO can collect Windows notifications, watch Git project status, monitor system health,
track selected processes, and announce reminders while it is running. Routine changes
are grouped into brief updates every 15 minutes. Reminders and low-battery alerts can
be delivered sooner. Speech waits until the microphone capture and current command finish.
Initial notification history is available in a briefing but is not announced as new.

## Voice

### Local listening and setup checks

```powershell
uv pip install --python .venv\Scripts\python.exe -r requirements-speech.txt
.venv\Scripts\python.exe main.py --setup-speech
.venv\Scripts\python.exe main.py --doctor
.venv\Scripts\python.exe main.py --mode local --calibrate
```

`--setup-speech` downloads a multilingual base model once. Normal listening loads
only a cached model using faster-whisper on the CPU with int8 computation, with a
voice-activity filter to reduce silence hallucinations. This is not perfect recognition:
noise, names and mixed-language speech can still be misheard. `STT_LANGUAGE=en` or `hi`
restricts the language; empty means automatic detection. `WHISPER_MODEL` chooses size.
Changing the model requires running setup again.

By default, unavailable local recognition falls back to Google's online recognizer,
which sends captured audio to Google. Set `STT_ALLOW_ONLINE_FALLBACK=false` to prevent
that. `STT_BACKEND=google` explicitly chooses online recognition; `whisper` retains
the legacy openai-whisper backend. Missing local models are reported once per five
minutes, not on every utterance. `--doctor` reports setup without recording audio or
reading mail; cached credentials are not described as a verified connection.

### Spoken voice

Install the optional dependencies in the same environment as ZENO:

```powershell
uv pip install --python .venv\Scripts\python.exe -r requirements-awareness.txt
.venv\Scripts\python.exe main.py --voice-preview
```

The default is `en-IN-NeerjaNeural`, a female voice, with slower pacing and reduced
volume/pitch. Change `TTS_VOICE`, `TTS_RATE`, `TTS_VOLUME`, and `TTS_PITCH` in `.env`.
For a British voice try `--voice en-GB-SoniaNeural --voice-preview`.

Neural speech sends the spoken text to Microsoft's online service using
[edge-tts](https://github.com/rany2/edge-tts). It needs internet and may occasionally
be unavailable. ZENO then falls back to the installed Windows Zira voice. Set
`TTS_BACKEND=sapi` for entirely local speech; `TTS_LOCAL_VOICE` selects its installed voice.

## Commands

| Say or type | Result |
| --- | --- |
| `Brief me` / `What's new` / `What did I miss` | Counts and useful changes from accessible sources |
| `Read my updates` | Reads titles/previews for up to five collected updates |
| `Summarize my updates` / `What needs my attention` | Gemini summarizes up to ten collected events into a short briefing |
| `Connection status` | Shows which sources are connected or unavailable |
| `Work status` | Changed/untracked file counts and unpushed commits in watched Git projects |
| `What's running` | Five largest running processes by memory |
| `Watch project C:\path\to\repo` | Watch that Git project's status changes |
| `Watch process 1234` | Report when that PID stops; an exit is not assumed successful |
| `Remind me in 10 minutes to submit my work` | Save a reminder; minutes and hours are supported |
| `Focus mode` / `Pause updates` | Collect changes without proactive speech |
| `Resume updates` | Resume grouped spoken updates |
| `Could you check my emails please?` | Collected Gmail/Outlook updates and explicit missing-connection status |
| `Any WhatsApp updates?` | Matching Windows notifications, not full chat access |
| `Tell me more` after a briefing | Reads previews from that briefing; context expires after five minutes |
| `Show my reminders` | Lists up to five pending reminders |
| `Remind me in five minutes to review ZENO` | Supports common spoken numbers as well as digits |

`Catch me up` and `Anything important?` also request an AI summary (the same Gemini
data disclosure as `Summarize my updates`). These are supported phrasing patterns,
not unrestricted conversational understanding. "Read" and follow-up detail requests
explicitly read previews; ordinary "check" requests use counts. Detail speech uses
the configured TTS service. Notification context stays separate from action history.

Scheduled quiet hours are off by default. Set `QUIET_HOURS=22:00-08:00` to mute proactive
speech during that period in the computer's local timezone, including reminders.
On-demand briefings still work during quiet hours.
Set `AWARENESS_ENABLED=false` to disable collection. `WATCH_PROJECTS` is a semicolon-separated
list of Git folders; it defaults to ZENO's own repository. Project monitoring notices Git
status changes, not every keystroke or edit to an already-dirty file.

This is an in-process monitor, not a Windows startup service: closing ZENO stops collection.
In desktop mode, closing the window can hide it in the tray; choose Quit ZENO to
stop the app. Desktop sources collect after the engine starts, but proactive spoken
digests are not currently dispatched there; request a briefing explicitly.
Text-console mode provides on-demand briefings; proactive speech is delivered between
voice interactions, or in server-only mode. Browser/mobile use through `main.py` shares
the same local awareness state. Starting the FastAPI module independently does not start collection.

## WhatsApp, Telegram, Discord, Gmail and Outlook notifications

The Windows notification source reads the notifications Windows exposes. It can include
any of those apps **when they actually send a Windows notification**. Enable notifications
in the app/browser and Windows. Browser notifications may be labeled Google Chrome or Edge.
This does not give ZENO access to chat history, muted chats, or messages that never generated
a notification. Messages received while ZENO was closed are recoverable only if still
present in Windows notifications or in a connected inbox's recent results.

Windows must grant notification access. `python main.py --briefing` checks access and prints
source status. An access failure is reported instead of being interpreted as "no messages."
Access requirements can vary by Windows app packaging; see Microsoft's
[notification listener documentation](https://learn.microsoft.com/en-us/windows/apps/develop/notifications/app-notifications/notification-listener).

Notification text is not passed to the action planner. Routine spoken digests include app
names/counts, not private message bodies. `Read my updates` explicitly reads previews and,
with neural speech enabled, sends that spoken content to the speech service. The collector
does not run an LLM on every poll. **`Summarize my updates` explicitly sends up to ten
collected titles/previews to your configured Gemini service for an AI briefing.** The reply
is spoken as a summary only, never interpreted as a request to act on notification text.

## Direct Gmail inbox connection

If Google Cloud shows **Google Cloud access blocked**, complete Google's required
two-step verification yourself, then refresh the console. Never paste verification
codes, passwords, refresh tokens or client JSON contents into a chat.

1. In Google Cloud, enable the Gmail API and configure the OAuth consent screen. For a
   testing app, add your own Google account as a test user.
2. Create a **Desktop app** OAuth client and download its client JSON outside the repository.
3. Run:

```powershell
.venv\Scripts\python.exe main.py --connect gmail --credentials "C:\path\to\client_secret.json"
```

If you save the Desktop client as `%LOCALAPPDATA%\ZENO\accounts\google-client.json`,
future connections can use `python main.py --connect gmail` without `--credentials`.
The browser sign-in window lasts ten minutes. Keep the command running until it confirms
connection. A refused localhost/127.0.0.1 callback can mean the listener has expired or
stopped: restart the connect command and use its **new** sign-in page, not an old callback URL.

Sign in through Google's browser page. ZENO requests `gmail.readonly` and polls only sender,
subject and timestamp metadata for up to 50 inbox messages received in the last day. It
does not read message bodies, send mail, delete mail, or mark messages read. A high-volume
inbox can exceed this polling window; this is not a complete mailbox archive.
Follow Google's [Python quickstart](https://developers.google.com/workspace/gmail/api/quickstart/python)
for OAuth setup. A Gemini API key alone cannot authorize access to Gmail.

For a new personal setup: select/create a dedicated ZENO project, open **APIs & services
→ Library → Gmail API → Enable**, then **Google Auth Platform**. Configure the app name
and your support/contact address, choose an external testing audience, and add your
own Gmail address as a test user. Under **Clients**, create a **Desktop app** client
named ZENO Desktop. Download the JSON outside the Git repository and use its local
path in the command above. Google may require reconnection as testing tokens expire;
do not treat that as an empty inbox. Review the consent screen yourself. The requested
`gmail.readonly` scope is broader than the metadata that this implementation fetches.

## Direct Outlook inbox connection

1. Register a Microsoft Entra application supporting the accounts you want to use, including
   personal Microsoft accounts if appropriate. Enable public-client/device-code authentication.
2. Configure delegated `Mail.ReadBasic` permission and set `OUTLOOK_CLIENT_ID` in `.env`.
3. Run `.venv\Scripts\python.exe main.py --connect outlook` and complete Microsoft's sign-in.

ZENO polls sender, subject and timestamp metadata from the latest 50 inbox messages. It
never requests send/write access. See Microsoft's [device-code Python tutorial](https://learn.microsoft.com/en-us/graph/tutorials/python)
and [message-list permissions](https://learn.microsoft.com/en-us/graph/api/user-list-messages?view=graph-rest-1.0).

In the [Microsoft Entra admin center](https://entra.microsoft.com/), sign in and open
**App registrations → New registration**. Name it ZENO Desktop; if you need personal
Outlook accounts, select the supported-account option that includes personal Microsoft
accounts. Under **Authentication → Advanced settings**, enable **Allow public client
flows** for device-code login. Under **API permissions**, add Microsoft Graph's
**delegated Mail.ReadBasic**, not application-wide permissions or Mail.ReadWrite.
Copy **Application (client) ID** from Overview into `OUTLOOK_CLIENT_ID` in the project's
`.env`. This flow does not need a client secret. Registration requires an Entra tenant
and permission to register apps; if your account cannot access that, direct Outlook
setup remains blocked, but Windows Outlook notifications can still work. Do not start
a paid subscription just to clear a setup screen.

## Storage and limits

Events and preferences live in `%LOCALAPPDATA%\ZENO\awareness.sqlite3`, outside the repository.
The briefing window is 24 hours; retention is capped at seven days and 1,000 records.
Account tokens live under `%LOCALAPPDATA%\ZENO\accounts` and are encrypted for the signed-in
Windows user using DPAPI. Do not commit OAuth client files or copy tokens between accounts.
`ZENO_DATA_DIR` can override the data directory. Revoke account access at Google/Microsoft
to disconnect. Windows notifications and direct inboxes can report the same mail separately.

Automatic prioritization uses explicit reminders, threshold crossings and grouped changes;
on-demand AI summaries can highlight attention items from the available previews. It does
not infer every deadline or learn a personalized priority model. Account connection
and notification coverage are always reported separately from system/project monitoring.
