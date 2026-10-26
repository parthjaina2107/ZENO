# Natural voice sessions

Start from the repository directory after installing the normal and speech dependencies:

```powershell
.venv\Scripts\python.exe main.py --setup-speech
.venv\Scripts\python.exe main.py --mode local --calibrate --wake-word
```

Say **Hey ZENO** and wait for “I'm listening”, or say **Hey ZENO, open Notepad**
as one phrase. After a response, the conversation stays open for 30 seconds so you
can ask a follow-up without repeating the name. The existing brain resolves references
using recent conversation and actual tool outcomes; ambiguous references still need
clarification. After inactivity, another wake phrase is required.

`--text` bypasses the wake gate and recognition checks. Omitting `--wake-word` keeps
the previous direct-listening behavior unless `WAKE_WORD_ENABLED=true` is configured.
`VOICE_FOLLOWUP_SECONDS` changes the session window (5–120 seconds).

Say **go to sleep** to return to wake standby, even from direct-listening mode.
This does **not** switch the microphone off: it must still capture audio to recognize
the next wake phrase. Exit ZENO to stop its microphone capture. If no local model is
available, ZENO explains the setup requirement rather than silently entering standby.

## What the wake feature is—and is not

This is a **transcript-based local wake gate**, not a trained low-power hotword detector.
It captures phrases and runs the cached Whisper backend, so recognition latency and CPU
use are higher than a dedicated wake-word engine. It cannot guarantee zero false wakes.
Standby recognition never uses Google's online fallback and does not log the ambient
transcript. Only accepted requests reach the brain. A missing local model blocks startup
in wake mode; use `--setup-speech` with `STT_BACKEND=faster-whisper` or use text mode.

While a session is open, the existing configured online recognition fallback still applies.
Set `STT_ALLOW_ONLINE_FALLBACK=false` to keep recognition local throughout. No new
always-on background service, startup entry, or desktop layer is installed.

## Recognition uncertainty

For faster-whisper, low decoder scores, high no-speech probability or repetitive decoding
trigger a readback: “I may have heard … Is that right?” Say **yes**, **no**, or repeat a
clear replacement request. The pending request expires after 20 seconds. An uncertain
confirmation does not approve it. These diagnostics are **heuristics, not calibrated
confidence percentages**; an incorrect transcript can still appear confident. Other
recognition backends currently provide no quality flag in this integration.

Confirming a transcript is not authorization for a destructive action: existing deletion
and shutdown/restart permission gates still apply separately.

## Interrupting speech (optional, headphones required)

Set `VOICE_BARGE_IN=true` in your `.env` only when using headphones and cached local
recognition. During ZENO's replies, say **stop**, **wait**, **stop speaking**, or
**Hey ZENO, stop**. These cancel the current and queued speech without closing ZENO.
“That's not what I meant” stops speech and invites a correction. Completed actions are
not automatically undone or replayed. Ordinary commands captured during speech are
discarded; repeat your new request once speech stops.

This mode has **no acoustic echo cancellation**: laptop speakers may feed ZENO's own
voice back into its microphone. It is off by default. Interruption takes effect after
phrase capture and local transcription, not instantly. Neural synthesis/playback and
Windows SAPI can be cancelled; the cross-platform pyttsx3 fallback may finish its current
utterance. No microphone capture runs during reasoning, task execution, or permission
handling through this feature. It is **speech interruption, not in-flight task cancellation**.
Ctrl+C remains the application exit control.

The console shows when the microphone is paused, listening, or capturing in standby /
interruption mode. This is a console indicator, not a tray icon or hardware mute light.
Responses remain concise by default; explicit detailed explanations may be longer.
