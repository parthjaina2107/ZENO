# Changelog

## Unreleased

- Added original JARVIS/Siri-inspired interaction refinements: Focused/Warm/Balanced
  assistant profiles, an island conversation-only toggle, focused Escape handling,
  a grounded capability guide, a state-reactive native orb and phase-specific copy.
  Actual microphone callbacks gate live capture feedback. Fixed native dashboard
  mode-selector pointer access. Setup reviewed/updated: restart/refresh; no new
  packages, accounts, voice models or environment settings. Explicit profile choices
  persist in existing memory; mode is session-only. Live hardware/provider checks
  remain pending; no commercial release or license decision is declared.

- Added Just talk mode for native/browser text and native on-demand voice, with
  a tool-free companion route, contextual conversational tone, synthetic examples,
  language matching, nonexclusive support and safety instructions. Added explicit
  conversation-style preferences and session context clearing. Memory changes
  now require direct instructions rather than incidental phrases. This configures
  the existing Gemini model; no fine-tuning, private-chat collection or new model
  is introduced. Setup/privacy/launch readiness reviewed for controls, saved style,
  provider context and pending human safety/quality evaluation; no new dependencies.

- Added a native coding-workspace specialist using an installed, signed-in Codex
  CLI independently of Gemini. Island requests and dashboard Coding task mode
  accept a literal project folder, read tutorial/source context, propose code and
  apply approved text changes with backups, stale-edit checks and read-back
  verification. Optional PDF support uses requirements-coding.txt; DOCX uses the
  standard library. VS Code launch is requested after saving. No training,
  generated-code execution or runtime test loop is performed. Setup/privacy/launch
  readiness reviewed for account/configuration, OneDrive roots, retained run data
  and pending real provider/OS checks. No settings migration is required.

- Redesigned the native island around OriginKit-inspired ribbon motion, reflective
  glass accents and a cursor ring field. Added icon-based quick-action tiles,
  animated button highlights and a footer; input/approval panels grow to fit.
  Hover expansion/collapse, focus rules, microphone lifecycle and the separate
  dashboard are retained. The effects are original Qt implementations rather than
  imported web source. Lucide 0.468.0 SVG icons and their ISC/Feather notices are
  bundled. Setup guide reviewed/updated: restart; no new packages or migration.


- Added a Glance-inspired matte-black island/workspace design, compact voice
  card, colored listening rim, measured level visualization and input-transparent
  screen-edge light with an entrance bloom and reactive pulse. Dashboard remains
  a separate window. Actual stream-open/close callbacks now control mic feedback;
  opening/permission failure, Stop and capture closure cannot leave it active.
  Reduced motion keeps a static capture indicator. Setup reviewed and updated:
  restart/refresh; no extra dependencies or settings migration. Visual previews
  simulate microphone activity; no live mic/provider success is claimed.


- Fixed unbounded SDK retry work behind reasoning timeouts: pass transport
  timeouts and disable nested retries; bound the fallback chain to a 36-second
  application budget with 12-second attempts. Report overload/timeouts, rejected
  credentials, quota and model failures distinctly without logging provider
  response bodies. Failed desktop reasoning is marked AI unavailable, with an
  explicit island Retry action; it is no longer recorded as a successful answer.
  Setup reviewed and updated: restart, no new credentials/dependencies/config.
  Live diagnostics found Gemini 503/timeouts; provider recovery is unverified.

- Removed the legacy white desktop assistant/settings window. The black dashboard
  is now the only full desktop window; its Preferences page includes shortcut
  recording/disable, microphone, pause, spoken replies, privacy information and
  Quit. Island Settings and tray Preferences open that same window. The compact
  island remains separate. Existing desktop.json settings are preserved; busy
  tasks block settings changes and shortcut conflicts preserve the old binding.
  Setup/desktop guides reviewed and updated: restart ZENO, no new dependencies.


- Separated the compact desktop island from the full dashboard. Dashboard opens
  only from its button or tray menu, in a separate resizable window sharing the
  same controller. Closing it leaves the island active. Qt WebEngine loads lazily.
- Fixed hover-away collapse using actual cursor coordinates across child controls:
  550 ms delay, smooth transition, preserved typed drafts and ongoing tasks.
  Pending approvals remain expanded. Strengthened the smoothed cursor highlight.
  Setup/desktop guides reviewed and updated; restart desktop mode, no settings
  migration or additional dependencies beyond the previous dashboard update.


- Replaced the island's small native content panel with the actual shared dashboard
  HTML/CSS/JS and glass artwork, including navigation, composer, conversation,
  activity, approvals, telemetry and media controls. Added a restricted local
  WebChannel bridge to the existing desktop controller; no HTTP server or token
  is required. Hover expands to a screen-fitted dashboard; reduced motion also
  disables native expansion. Dashboard session data stays in memory.
- Setup updated: quit ZENO and reinstall `requirements-desktop.txt` before
  restarting. Adds pinned PySide6-Addons and PySide6-WebEngine alongside Essentials.
  Native voice and task execution retain their existing behavior; provider and
  microphone smoke checks are still manual. No commercial readiness claim.


- Desktop island now mirrors the dashboard's charcoal glass layers, silver
  borders and white actions, with cursor-following lighting, drifting ambient
  highlights and a smooth, reversible hover expansion/content fade. Hidden
  islands stop their visual timers. Setup guide reviewed and updated: restart
  desktop mode; no new dependencies or settings migration.

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

### Monochrome web theme

- Replaced champagne colours with a high-contrast black, white and silver palette,
  including monochrome hero artwork, cursor lighting, controls and dialogs.
- Setup reviewed: no dependencies, configuration or backend changes. Refresh the
  browser after restarting an older server to load the updated stylesheet.

### Persistent desktop island

- Desktop mode now starts with an always-on-top monochrome island. Hover expands
  it for voice start/stop, typed requests, replies and request-bound approvals.
- Shortcuts no longer open the main window. Settings remain available from the
  island and tray. Closing settings leaves the island accessible.
- Idle completion collapses the island instead of hiding it. Uncertain speech
  remains a draft; pending approvals stay visible with the complete prompt.
- Setup and desktop guides updated. Restart desktop mode to apply. No dependency,
  credential or automatic Windows-startup changes are needed.
