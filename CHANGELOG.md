# Changelog

## Unreleased

### Added

- Floating activity panel glass styling: neutral translucent surface, faint
  border, soft shadow and muted monochrome voice bars. Setup reviewed: no installation or
  configuration changes; restart ZENO to see the updated styling. This is a
  painted glass effect, without native desktop background blur.

- Non-activating floating desktop panel with live microphone levels, recognized
  command, response and stage indicators; automatically hides after completion.
- Adjustable end-of-command pause: 0.6s default, 0.9s balanced or 1.4s relaxed.
  Speech-model loading overlaps recording; per-stage latency is logged locally.
  Setup guide reviewed and updated. Restart desktop mode to use these changes;
  no new dependencies or credentials are needed. Existing settings adopt 0.6s.

- Native Windows press-to-talk desktop app with a user-selected global shortcut,
  Apple-inspired settings, typed fallback, microphone choice and system tray.
- The same shortcut cancels recording, speech and remaining task steps. Started
  OS calls drain before another request; completed changes are not undone.
- Desktop approval cards with request-bound responses, expiry and high-risk
  double confirmation; uncertain recognition becomes a draft for user review.
- Optional local wake-word conversation windows and headphone speech interruption
  for the CLI, with local-only standby recognition and uncertainty handling.
- Setup, privacy, support, security and commercial launch-readiness documentation;
  contribution/agent instructions and PR checks require setup review with changes.
- Windows CI and local documentation validation.

### Setup and upgrade notes

- Existing users must install `requirements-desktop.txt` to use `--desktop`, then
  choose a shortcut. `Start-ZENO.cmd` opens desktop mode without a terminal.
- The desktop Qt dependency is pinned to the version used for development checks.
- Install `requirements-speech.txt` and run `--setup-speech` for the local model;
  install `requirements-awareness.txt` for neural voice/account integrations.
- `WAKE_WORD_ENABLED`, `VOICE_FOLLOWUP_SECONDS` and `VOICE_BARGE_IN` are documented
  in `.env.example`. Desktop activation uses its shortcut instead of a wake word.
- The example ngrok token is now empty so a fresh installation does not try to
  authenticate a tunnel using placeholder text. Existing configuration is preserved.
- Upgrade by quitting ZENO, pulling without discarding local edits, reinstalling
  selected dependencies and comparing `.env.example`; see `docs/setup.md`.

Licensing remains undecided. No commercial product release is declared here.

### Glass workspace and backend integration

- Added the responsive champagne glass workspace, cursor illumination, editable
  voice drafts, session activity, preferences, exact approvals and live telemetry.
- Added bounded web agent planning, interruption, media commands and task progress.
- Preserved the latest device registry, native desktop, awareness and contextual
  conversation work while merging the web interface. Browser authentication now
  supplies a stable random device identity; revoked connections are rejected.
- Web commands explicitly signal completion so intermediate results do not make
  the composer available while a multi-step command still runs.
- Setup reviewed and updated in docs/setup.md. Restart the server and refresh the
  browser; old sessions may require sign-in. Existing credentials remain in .env.
  No frontend build step is required. Hardware/provider and commercial-release
  checks remain outstanding in the launch-readiness guide.
