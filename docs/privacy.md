# Data and privacy overview

This describes the current source preview, not a completed commercial privacy
policy. The launch checklist includes the product policy, consent and data-control
work still required. Defaults below are those in `.env.example`; review your own
configuration before using private content.

## Data flows

| Feature | Data handled and destination |
| --- | --- |
| Desktop recording | Opens only after activation; PCM audio is held for transcription, and recording closes before reasoning/execution/speech |
| Local faster-whisper | Processes audio on the computer using a cached model; setup downloads model files |
| Google recognition fallback | Enabled in the example; captured audio can go to Google's online recognizer. Set `STT_ALLOW_ONLINE_FALLBACK=false` to disable fallback |
| Gemini reasoning | Sends relevant requests, recent context, saved facts and selected tool observations to the configured Google service |
| Screen interpretation | Captures a screenshot and sends it to Gemini when a screen question uses that feature |
| Edge neural speech | Sends the text to speak to Microsoft's online speech service via edge-tts; `TTS_BACKEND=sapi` selects installed local speech |
| Gmail/Outlook | After sign-in, queries sender/subject/time metadata. The Gmail scope is broader than the fields currently fetched |
| Windows notifications | Collects the notification text Windows exposes; this can include private previews |
| AI update summaries | Explicit summary requests can send up to ten collected titles/previews to Gemini; routine polling does not call the LLM |
| Spoken update details | A readout can send private previews to online TTS when enabled |
| Remote browser/tunnel | Commands, results and approvals pass between the browser and running server; a configured ngrok tunnel adds an external service |

The desktop interface does not save recordings. The legacy `whisper` backend may
use a temporary WAV file during transcription and attempts to remove it afterward.
Requests and tool details can still appear in local memory, logs and reports.

The preview does not implement a ZENO-owned cloud analytics backend. External
providers have their own data practices and terms. Local processing options do not
make Gemini, connected-mail or explicitly enabled remote features offline.

## Local storage

| Default location | Contents / lifecycle |
| --- | --- |
| Project `.env` | API configuration and remote secrets; retained until you change/remove it |
| `%LOCALAPPDATA%\ZENO\.env` if present | Older saved configuration fallback; not automatically removed by uninstalling a checkout |
| `%LOCALAPPDATA%\ZENO\desktop.json` | Shortcut, input-device index and spoken-reply preference |
| `%LOCALAPPDATA%\ZENO\accounts\*.token` | OAuth credentials; encrypted for the current Windows user with DPAPI |
| `%LOCALAPPDATA%\ZENO\awareness.sqlite3` | Collected events/preferences/reminders; event retention is capped at seven days and 1,000 records |
| `%LOCALAPPDATA%\ZENO\models` | Downloaded speech-model cache |
| Project `zeno_memory.json` | Saved personal facts/preferences; recent conversation context is held in process memory |
| Project `audit_log.jsonl` | Action parameters, permission decisions and execution results; no built-in retention limit |
| Project `task_reports` | Goal details and task evidence; no built-in retention limit |
| Project `screenshots` | Screenshots requested through the screenshot tool; no built-in retention limit |
| Project `paired_devices.json` | Remote paired-device state |
| Project `voiceagent.log` | Diagnostics; default rotating files are 5 MiB with five backups |

`ZENO_DATA_DIR`, `MEMORY_FILE` and `LOG_FILE` can change some of these locations.
The source preview does not yet put all runtime state in one per-user directory.
Keep the checkout and data directory protected like other personal documents.

## Stop collection, disconnect or remove local data

Quit all ZENO interfaces before changing or removing runtime files. Desktop
window close may only hide it in the tray; choose **Quit ZENO**. A task cancellation
stops that request, not previously enabled background awareness collection.

Set `AWARENESS_ENABLED=false` and restart to disable awareness polling. Revoke
connected access in your Google/Microsoft account settings to disconnect the
provider. Removing a local token alone does not revoke its grant at the provider.
Review Windows notification access separately if you enabled it.

There is no unified erase-account or uninstaller UI yet. To remove local data,
first back up anything you want to retain, identify the actual configured paths,
and remove only the relevant generated files/directories listed above. Do not
delete unrelated project files. Revoke or rotate API keys if you want them to stop
working. Copies already sent to providers follow those providers' policies;
deleting local files does not delete remote copies automatically.

Never attach raw `.env`, OAuth JSON/tokens, logs, screenshots, memory files, event
databases or task reports to a public issue. Redact private content before sharing
diagnostics. See [SECURITY.md](../SECURITY.md) for vulnerability reporting.
