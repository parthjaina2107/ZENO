# ZENO desktop: press to talk

This optional Windows interface uses the existing ZENO brain, tools, permissions,
voice settings and awareness sources. It does not start the remote-control server.
CLI, text and wake-word modes remain available separately.

## Start

For a fresh checkout, first follow the [complete Windows setup guide](setup.md).

From the project directory, with the normal project requirements already installed:

```powershell
uv pip install --python .venv/Scripts/python.exe -r requirements-desktop.txt
.\.venv\Scripts\python.exe main.py --desktop
```

Alternatively, double-click `Start-ZENO.cmd` after installing dependencies. It
opens the app without a terminal. No automatic startup is enabled.

1. Hover over the island, choose **Preferences** to open **Preferences** in the black dashboard.
2. Click the shortcut field, press your preferred combination, then **Save settings**.
3. Press that shortcut from any app to begin one voice request. Speak, then pause
   naturally to send it. Do not press the shortcut to submit the recording.
4. Press **the same shortcut again while busy** to stop recording, reasoning,
   remaining actions or spoken output. The on-screen Stop button also works;
   Escape stops a request while ZENO has focus.

There is deliberately no preassigned shortcut. Try a combination such as
Ctrl+Shift+Y, but check for conflicts with your own apps. NVIDIA's overlay can
react to Alt+Z combinations even when Windows does not report a registration
conflict. Windows-key combinations, F12, plain letters and common editing
shortcuts are rejected. Other function keys can be used on their own (some
laptops also require Fn). Holding the key does not repeatedly start/stop ZENO.

Closing the window hides it in the system tray when the tray is available.
Choose **Quit ZENO** in the tray menu or About page to exit and release the
shortcut. A second desktop instance is blocked; look for the existing tray icon.
Changing a shortcut that Windows reports as unavailable keeps the previous one.

## What stopping means

Only one request runs at a time. Cancellation is checked before actions and after
reasoning, transcription and approval. A cancelled model response cannot start
later actions. Pending approvals are invalidated. Speech is interrupted, and
recording is discarded and closed between audio buffers.

Already-started OS calls are allowed to finish safely; completed actions are not
undone. ZENO displays **Stopping** while in-flight workers drain and does not
start another request in that period. Slow speech-model loading, a device driver,
or an already-issued network request can delay the return to Ready. This is not
a force-kill switch for other applications. It does not suspend background mail
or system-awareness polling already enabled in your ZENO configuration.

Routine actions use the existing permission policy. Deletion and shutdown/restart
still require approval in the desktop UI. High-risk actions require a second
confirmation. Approvals expire after 60 seconds and cannot be reused by another
request. No terminal confirmation prompt is used in desktop mode.

## Voice and privacy

- Microphone capture is **off until explicit activation**, including at startup.
  There is no continuous wake-word capture or voice barge-in in this interface.
- There are 15 seconds to start speaking and a 25-second phrase limit. About
  0.6 seconds of silence ends the phrase by default. Choose 0.9 or 1.4 seconds
  in **Voice & microphone** if you need longer pauses within a sentence.
- Choose an input device and enable/disable spoken replies in **Voice & microphone**.
  Changes apply to the next request. Existing soft voice/rate settings are preserved.
- Low-confidence transcripts are shown as an editable draft, never executed
  automatically. Review and Send, or start a new recording.
- Local speech recognition uses the existing STT configuration. If online
  recognition fallback is enabled, captured audio may be sent to that provider.
  Model prompts use your configured AI provider. Edge neural TTS is online.
- The desktop interface does not save recordings. Existing memory, audit logs
  and task reports may retain request text and task details, just as in CLI mode.
- Desktop preferences live in `%LOCALAPPDATA%\ZENO\desktop.json` (or your
  configured `ZENO_DATA_DIR`). API keys and OAuth tokens are not stored there.

## Troubleshooting

The desktop island and full dashboard are separate interfaces. Desktop mode starts
only the compact, always-on-top pill. Hover expands a small quick-access panel
with Talk/Stop, typed input, replies and approvals. **Open workspace** opens the full
workspace in its own normal, resizable window; it never opens on hover. The tray
also offers **Open dashboard**. Both interfaces share one desktop controller.
Closing the dashboard hides that window without stopping the island or a task.

Move the pointer away to collapse the island after 550 milliseconds, followed by
a smooth resize. Cursor position is checked across all child controls, avoiding
stuck hover states. The silver highlight follows the cursor with smoothing.
Leaving while typing preserves the draft; choose Type a request again to resume.
Leaving during a task collapses the panel without cancelling work; Stop remains
available in the pill. Pending approvals deliberately keep the panel expanded.
Hover does not take keyboard focus; choosing Type a request does.

**Talk** starts native recognition; speaking then pausing submits a request.
Uncertain recognition stays an editable draft. The full dashboard uses the same
native task controller and native voice behavior; its separate browser Single
command mode is unavailable. Sensitive actions still require request-bound
approval, including two confirmations for high-risk actions. Be explicit about
opening target applications for keyboard actions from either typing interface.

Choose **Preferences** on the island for Preferences in the same black dashboard.
Shortcut, microphone, pause and spoken-reply controls are all on this page.
There is no separate desktop settings window. **Save settings** persists these
choices in the existing desktop preferences file; changes apply on the next request.
The dashboard's Preferences includes reduced motion, which also disables island
expansion animation and cursor light for the session. Voice configuration is saved from this same Preferences page. The dashboard loads bundled HTML, CSS, scripts and artwork
through Qt WebEngine, with remote navigation blocked. No HTTP server or token is
needed. Dashboard history/preferences remain session-only; desktop settings use
their existing persistent location.

Drag the island header to reposition for the session. Screen changes reset its
top anchor. Quit from dashboard Preferences or the tray. Windows sign-in startup is unchanged.
Command/reply excerpts can be visible during screen sharing. The painted island
glass does not blur the Windows desktop behind it.

The configured speech model loads concurrently with recording and is reused for
subsequent requests. Capture stays activation-only. No additional model download
or provider change is introduced. Stage durations (without request text) are logged
under `VoiceAgent.Desktop.Latency`; use these to distinguish transcription, model,
tool and speech delays. Actual speed depends on CPU, model, network and tool work;
no fixed cloud response time is guaranteed. Cancellation still drains workers.

- **No response to the shortcut:** confirm ZENO is running, save a different
  combination and check for overlays or other apps using the keys. The button
  and text input are always available. Global shortcuts cannot operate on the
  Windows lock screen or secure desktop/UAC prompt.
- **Microphone unavailable:** choose a connected input device in settings and
  check Windows microphone permissions yourself. Unplugged devices may need
  reselecting after restarting ZENO. Use typed requests as a fallback.
- **Recognition slow or unavailable:** run `python main.py --doctor`; install
  `requirements-speech.txt` and run `python main.py --setup-speech` if needed.
- **Reasoning unavailable:** the desktop uses the same configured Gemini key
  and models as CLI. This feature does not switch providers or remove API limits.
  `AI unavailable` means the reasoning request failed even if the dashboard is
  connected to the local controller. On an outage, the island offers **Retry**
  for the same request after it becomes idle. The failed request does not execute
  actions. A 503 indicates provider overload; retry later. Authentication, quota
  and unavailable-model failures have distinct messages. Direct local commands
  remain available; retries are explicit rather than a background monitor.
  Provider errors are displayed without speaking a long fallback message, so the
  island returns to Retry promptly.
- **Launch fails without a terminal:** run the Python command above to see errors.
  Dependencies must be installed in the project's `.venv`.

## Development verification

`tests/test_desktop.py` covers settings, no startup microphone access, shortcut
validation/conflict recovery, late inference cancellation, pending approvals,
sequential action cancellation, audio cleanup, uncertain transcripts and speech
interruption. Optional Qt tests skip when desktop dependencies are not installed.
Live microphone recognition accuracy still depends on the user's voice, device
and room; test a harmless command such as “what time is it” after setup.

## Reactive notch interface

The island uses matte-black surfaces, a soft cursor spotlight and a colored
listening rim inspired by the Glance reference. The dashboard keeps its own
window and uses the same dark utility panels, compact voice card and muted
controls. Color is concentrated in active microphone feedback.

Voice activation first shows **Opening microphone**. The colored rim, microphone
label, level meter and screen-edge light start only after the audio stream opens.
The entrance bloom settles into a gentle pulse that responds to the measured
microphone level. The edge light is transparent to mouse input and does not take
keyboard focus. It follows the screen containing the island. Closing capture,
Stop, cancellation and errors clear the light; speaking a reply does not turn it
on. This is capture feedback, not an OS permission dialog or permission grant.

Reduced motion removes the entrance pulse, moving rim and changing edge-light
animation while retaining a static active indicator. No extra packages, automatic
startup or continuous microphone listener are added. Restart desktop mode and
refresh the web dashboard to load the design. Native microphone permissions and
recognition accuracy remain manual checks; UI previews use simulated levels.

## OriginKit-inspired island

The native island now uses a compact status pill, reflective brand mark, a
ribbon-lit voice card, pointer-reactive capsule field, two quick-action tiles and
a small footer. **Type a request** focuses the input; **Open workspace** opens
the separate black dashboard. **Preferences** opens dashboard Preferences and
**Minimize** returns to the pill. Hover-away collapse and request-bound approvals
retain their existing behavior. The panel grows to fit typed input and approval
controls, within the available screen size.

These are original Qt adaptations of OriginKit's visual/motion references, not
embedded web components. Runtime drawing is local. Lucide icons are bundled with
their upstream license; no web downloads or new packages are needed. Reduced
motion stops ribbon drift, pointer rings and button hover transitions while
retaining static capture indicators. See [reference and validation notes](originkit-island.md).

## Coding tasks

Select **Coding task · Codex** in the native dashboard, enter a full project folder,
and describe the tutorial/change. The island accepts requests such as
`Open VS Code and write Tutorial 3 in "C:\Users\HP\OneDrive\Desktop\etc"`.
This route uses Codex independently of Gemini, with context consent, reviewed file
proposals, backups and static/read-back verification. It does not run generated
code or tests. See [coding workspaces](coding-workspace.md) for setup and limits.

## Just talk

Select **Just talk** to keep dashboard text/native microphone requests inside a
conversation-only route. No desktop actions or fact writes run in this mode.
On the island use `Chat: ...` or `Can we talk?`; voice remains activation-only.
For actions switch the dashboard mode or send a separate explicit task request.
See [companion styles, context clearing and limits](companion.md).

## Orb, modes and response profiles

The native orb labels the actual request phase; only stream-open callbacks enable
live capture indicators. The island Assistant/Just talk switch applies to its text,
Talk button and shortcut for the current session. Escape while focused stops busy
work or collapses idle UI. Dashboard Preferences offers persistent assistant
profiles; its mode selector is independent of the island. See
[assistant experience](assistant-experience.md) for the full interaction notes.
