# Changelog

## Unreleased

### Added

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
