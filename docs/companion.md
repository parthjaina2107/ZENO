# Talking with ZENO

Choose **Just talk** in the dashboard to chat about your day, interests, learning,
creative ideas, good news or difficult feelings. The same mode works for typed
messages and the native dashboard's on-demand voice button. On the island or CLI,
prefix a message with `Chat:` or say `Can we talk?`. Ordinary emotional openings
such as `I feel lonely` also take the conversational path. No extra model install
or account is needed beyond the existing Gemini configuration.

The companion uses the existing model with system instructions and synthetic
tone examples. This is behavior configuration, **not fine-tuning or model training**.
ZENO does not collect chat for a training dataset or update model weights. External
provider data handling is governed by that provider's policies, not this statement.

## Controls

- **Just talk** is conversation only. Mentioning an app, command or file cannot
  execute it in this mode. Switch to **Agent task**, **Single command** or native
  **Coding task** when you actually want computer actions. Native chat voice
  capture keeps the conversation-only boundary after transcription.
- Type `Chat: I just want to vent, no advice` or `Chat: distract me with a story`.
  Responses should follow that preference and match your language, including
  Hindi/Hinglish. This is model behavior, not a guaranteed emotion detector.
- In normal command mode say `conversation style gentle`, `conversation style
  playful`, `conversation style direct` or `conversation style balanced`. This
  explicit preference is saved in the existing memory file. Current mood/request
  takes priority over a playful tone. In Just talk, style requests are conversational
  context rather than persistent preference changes.
- `clear conversation` (also in Just talk) clears the brain's in-process context
  and pending conversational clarification. It does not delete saved facts,
  displayed messages, terminal output, provider data or another interface's copies.
- Existing Stop controls cancel the request/speech. Each native voice turn still
  requires activation; this adds no ambient listening or emotion surveillance.

Recent dialogue stays in a bounded in-process window (12 entries, about six
exchanges). Connected interfaces share the same brain context; this preview does
not provide separate private conversation profiles for different people using one
running ZENO instance. Personal facts are saved only through explicit memory commands outside
conversation-only mode. Incidental/negated phrases containing “remember” are not
memory-store instructions. Saved facts remain available as model context. Use
existing recall/forget controls to manage them.

## Support and limits

ZENO should listen without shaming, avoid forced positivity and ask at most one
useful follow-up. Loneliness alone is not treated as an emergency. It should avoid
claiming human feelings, romantic attachment, exclusivity, professional credentials
or secrecy. It should support real-world relationships and personal choice.

For credible immediate danger, instructions prioritize immediate human help and
safe next steps. ZENO cannot diagnose, provide treatment, monitor safety, contact
emergency services or guarantee crisis detection. A small English phrase fallback
can offer immediate-help guidance during an outage; it is not multilingual crisis
detection. Otherwise an outage produces a transparent limited response rather than
pretending an offline model is available. No helpline directory is integrated.

Conversation text, recent context and explicitly saved facts go to the configured
Gemini service. Online speech recognition/TTS can send audio/replies to their
providers. Messages can remain in the UI or terminal; diagnostics from other
features may also retain content. This is not a confidential health service.
See [privacy](privacy.md) before sharing sensitive information.

## Verification

Automated tests use fake providers to check that chat cannot invoke tools or save
facts, context carries across turns, explicit style preferences persist, clearing
context preserves saved facts, and outages do not expose exception text. They also
check native voice and authenticated browser routing. These are software contract
tests, not proof of empathy, clinical safety or broad language quality.

[Synthetic conversation scenarios](../evals/companion-cases.json) provide a human
review set for loneliness, humor, grief, disagreement, language, dependency and
crisis responses. They contain no real conversations. Actual provider evaluation,
age-appropriate behavior, multilingual safety, accessibility and clinical/security
review remain pending. Do not call this a trained mental-health product or mark
commercial launch checks complete based on the prompt or unit tests.
