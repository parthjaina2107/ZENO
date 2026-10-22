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

1. Open **Keyboard shortcut**.
2. Click the shortcut field, press your preferred combination, then **Save shortcut**.
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
  0.9 seconds of silence ends the phrase automatically.
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
- **Launch fails without a terminal:** run the Python command above to see errors.
  Dependencies must be installed in the project's `.venv`.

## Development verification

`tests/test_desktop.py` covers settings, no startup microphone access, shortcut
validation/conflict recovery, late inference cancellation, pending approvals,
sequential action cancellation, audio cleanup, uncertain transcripts and speech
interruption. Optional Qt tests skip when desktop dependencies are not installed.
Live microphone recognition accuracy still depends on the user's voice, device
and room; test a harmless command such as “what time is it” after setup.
