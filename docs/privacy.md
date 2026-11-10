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
| Google recognition fallback | Disabled by default; if enabled, captured audio can go to Google's online recognizer. Set `STT_ALLOW_ONLINE_FALLBACK=false` to disable fallback |
| Local Ollama reasoning | Sends relevant requests/context to the loopback server on this PC; model setup downloads weights, inference does not require cloud |
| Gemini reasoning | Disabled by default; confirmed free-cloud mode sends relevant requests, recent context, saved facts and selected tool observations to Google; free-tier terms may permit product improvement use |
| Screen interpretation | Interprets requested screenshots using a local Ollama vision model or Gemini in enabled free-cloud mode |
| Edge neural speech | Sends the text to speak to Microsoft's online speech service via edge-tts; `TTS_BACKEND=sapi` selects installed local speech |
| Gmail/Outlook | Polls inbox metadata. Explicit Gmail commands can read message text and, with compose permission, save drafts and send reviewed messages |
| Windows notifications | Collects the notification text Windows exposes; this can include private previews |
| AI update summaries | Explicit summary requests send up to ten collected titles/previews to local Ollama or, when enabled, Gemini; routine polling does not call the LLM |
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
| `%USERPROFILE%\.ollama\models` | Local reasoning model weights; remove through Ollama when no longer needed |
| Project `.env` | API configuration and remote secrets; retained until you change/remove it |
| `%LOCALAPPDATA%\ZENO\.env` if present | Older saved configuration fallback; not automatically removed by uninstalling a checkout |
| `%LOCALAPPDATA%\ZENO\desktop.json` | Shortcut, input-device index and spoken-reply preference |
| `%LOCALAPPDATA%\ZENO\accounts\*.token` | OAuth credentials; encrypted for the current Windows user with DPAPI |
| `%LOCALAPPDATA%\ZENO\awareness.sqlite3` | Collected events/preferences/reminders; event retention is capped at seven days and 1,000 records |
| `%LOCALAPPDATA%\ZENO\models` | Downloaded speech-model cache |
| Project `zeno_memory.json` | Saved personal facts/preferences; recent conversation context is held in process memory |
| Project `audit_log.jsonl` | Action type and ID, source, timestamps, permission decisions and success status; no built-in retention limit |
| Project `task_reports` | Task status, step identifiers and verification flags; no built-in retention limit |
| Project `screenshots` | Screenshots requested through the screenshot tool; no built-in retention limit |
| Project `paired_devices.json` | Remote paired-device state. The adjacent `paired_devices.lock` coordinates writes. |
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

The Windows installer adds an uninstaller in Settings → Apps. Uninstalling retains
personal data. To remove local data,
first back up anything you want to retain, identify the actual configured paths,
and remove only the relevant generated files/directories listed above. Do not
delete unrelated project files. Revoke or rotate API keys if you want them to stop
working. Copies already sent to providers follow those providers' policies;
deleting local files does not delete remote copies automatically.

Never attach raw `.env`, OAuth JSON/tokens, logs, screenshots, memory files, event
databases or task reports to a public issue. Redact private content before sharing
diagnostics. See [SECURITY.md](../SECURITY.md) for vulnerability reporting.

## Coding-workspace data

Native coding requests send filtered source/tutorial context to the signed-in
Codex provider after consent. Common secret filenames are excluded, but source can
still contain private data; this is not a secret scanner. ZENO_DATA_DIR/coding_runs
(normally %LOCALAPPDATA%\ZENO\coding_runs) retains goals, paths, schemas, provider
events, proposed code, reports and backups. Older audit logs and task reports
may contain action arguments, diff previews or file text. Updating ZENO does
not rewrite those files. Review them locally before sharing diagnostics.
Temporary snapshots are removed after planning. There is no automatic retention
cleanup. Deleting run data does not erase project files or provider-side copies.
See [coding workspaces](coding-workspace.md) before approving sensitive source.

## Companion conversations

Just talk uses local Ollama or explicitly enabled free-tier Gemini with recent in-process context and
explicitly saved facts. ZENO adds no training-data capture or fine-tuning pipeline;
provider policies still govern provider-side handling. Recent context is bounded
to 12 entries. Explicit conversation-style preferences persist in the existing
memory file. Conversation-only messages do not write facts or run tools.
`clear conversation` clears brain context but not saved facts, visible dashboard
messages, terminal output or provider copies. Online recognition/TTS still follow
the existing flows above. No confidential health-service guarantee is made.
See [companion details](companion.md) before sharing sensitive experiences.

Assistant profile choices are explicit preferences stored in the same memory file
as conversation style. They affect model instructions, not voice recordings or
model weights. The island mode is session-only. No new training capture, analytics
or data destination is added by the orb/profile controls.


Explicit Gmail searches fetch up to five sender/subject/date results from Gmail.
Reading a numbered result fetches up to 6,000 characters of mail text. The mailbox
handler keeps numbered search results in session memory and returns replies to the
interface and configured speaker. These results bypass action planning and saved
conversation memory. Background Gmail polling continues to collect metadata only.

On-demand screen reading captures one primary-monitor screenshot. Local vision
sends it to Ollama on loopback. Opt-in cloud vision can send it to Gemini.
Screen replies are displayed or spoken and bypass saved assistant memory.

With optional Gmail compose permission, ZENO saves the reviewed message in
your Google account and sends it when you provide the draft's confirmation code
or click **Send reviewed draft** in the desktop app.
AI-assisted writing sends the topic you supply to the configured reasoning model.
The draft preview is visible to the requesting interface and may be spoken aloud.
Paired remote controllers can use these mailbox features on the host account.

The native dashboard stores per-feature access choices in `ZENO_DATA_DIR/app-access.json`.
Fresh profiles start with optional tools off. Disabling a source blocks new requests
and filters its collected events from subsequent briefings. OAuth grants and stored
events can be managed separately. New CLI voice captures omit full transcripts from
the normal application log. The optional headphone interruption listener accepts
only local stop or correction intents while ZENO is speaking.
