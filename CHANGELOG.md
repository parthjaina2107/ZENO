# Changelog

## Unreleased

- Moving the cursor off the expanded island immediately starts a gentler
  460 ms closing animation. Setup reviewed; no configuration change is needed.

- The docked island curves slightly outward where it meets the screen edge.
  Setup reviewed; this is a visual change only.

- The island now meets the top of the monitor with no transparent gap or
  horizontal border across its top edge, including during expansion.

- The desktop island has square upper corners and rounded lower corners at its
  existing sizes. Setup reviewed; the shape changes only how the window is drawn.

- Music now has a dedicated black pill that expands on hover into a player with
  album art, elapsed and remaining time, and Windows playback controls. Restart
  desktop mode to load the new layout.

- The native island shows the current track, artist and playback timeline for
  supported Windows players. Compact task updates and microphone capture take
  priority. Enable Media and volume in App access to display playback.

- App access now confirms each switch separately. Changing another permission or
  refreshing the page while a save is pending keeps the selected switch in place.
  Setup reviewed. Reopen ZENO to load the updated dashboard and controller.

- Removed the moving background light and layered backdrop filters from the native
  dashboard to reduce flicker during hover and scrolling. Setup was reviewed.
  Reopen ZENO to load the updated dashboard assets.

- Added App access to the desktop dashboard, with per-user switches for supported
  accounts, applications, device controls, AI services and background sources.
  Fresh profiles require opt-in. Review the setup guide and enable desired tools.
  Configured AI providers can be enabled in a running desktop session.
- Added one-click exit on the island and dashboard. Typing can interrupt reply
  playback. Folder and mail requests can run in sequence. Gmail now retains the
  recipient and content across clarification turns and checks cancellation before
  submitting a send. Reviews accept spoken digits and normalized email addresses.
  The island and dashboard can send the reviewed version with a button when
  speech recognition misses the command.
- Desktop shutdown disposes the dashboard's embedded browser before ending the
  Qt event loop. Setup reviewed. The existing Exit buttons use this shutdown path.
- Fixed trailing command qualifications, polite wrappers, wake/stop handling,
  folder acknowledgements, unverified remote outcomes, steady-noise capture,
  pause/resume semantics and Gmail date filters. Removed broken Aurora links.
  Install updated requirements for Windows media controls. App access settings
  live in ZENO_DATA_DIR; see the updated setup and privacy guides.

- Gmail supports saving drafts with dictated text or an AI-written subject and
  body. A draft preview and its session-specific code control sending.
  Existing read-only connections can opt in using `--connect gmail --gmail-compose`.
- Added on-demand local screenshot interpretation using Ollama's vision API.
  Install the vision model and restart ZENO. The default `OLLAMA_VISION_MODEL`
  is `qwen3-vl:2b`. Screen replies bypass planner memory. Setup, environment
  and privacy documentation updated.

- Added on-demand read-only Gmail searches and numbered email reads through the
  desktop, CLI and remote command handler. Results bypass OS action planning and
  persistent chat memory. Background polling continues to fetch metadata.
  Setup and privacy guides updated. Restart ZENO after updating. Existing
  gmail.readonly connections work, and expired connections need Google sign-in
  again. No new dependency or scope is required.

- Fixed negative and hypothetical requests turning into actions, ambiguous voice
  answers granting permission, and remote folder clarifications losing their
  plan approval. Remote approvals now require the matching action ID. Busy,
  oversized and failed browser requests show a terminal result.
- The local CLI and remote executor now share command ownership in combined
  mode. Cancellation waits for a started system action. Folder moves verify the
  path actually used. Browser and Windows operation failures reach the caller.
  Mute and unmute request the corresponding Windows audio state.
- App launch resolves installed executable names. Coding snapshots filter Google
  OAuth client files and ZENO runtime data. The legacy background launcher now
  accepts its forwarded launcher flag, and CI installs the PDF test dependency.
- Setup reviewed and updated. Reinstall requirements in the ZENO environment,
  remove retired python-jose and ecdsa packages, and refresh remote clients.
  PyJWT uses the existing HS256 key and device claims. The Pillow, oauthlib and
  pyasn1 dependency versions include advisory fixes.

- Fixed command chaining, diagnostic executable selection and file destination
  collisions. File creation and coding edits publish fully written files.
  Literal terminal commands work offline and return the diagnostic output.
  Closing an app targets its exact executable. Explicit remote agent folder
  requests use plan approval.
- Remote sessions now expire while connected. Re-pairing cannot reactivate an
  older token. Device updates serialize across workers, expired login lockouts
  reset, and each connection has its own clarification and chat history.
  The audit dashboard reads a bounded tail and reports unreadable records.
- The island stays open during typing, scrolls on shorter displays and keeps
  its controls on screen during expansion. The dashboard follows live system
  motion changes. Setup reviewed and updated. Restart ZENO to load these fixes
  and sign in again on remote browsers. No new packages are required.

- Thinned the island's chrome border again, from 1.5px to 0.75px, with proportional
  bevel strokes. Setup reviewed: drawing-only adjustment; restart desktop mode
  to load it. No dependencies, configuration or migration changes.

- Halved the island's chrome band from 3px to 1.5px, including its bevel strokes.
  Reflections now travel around the complete perimeter in a faster, seamless
  approximately 12-second loop, with matching start/end colors. Reduced motion
  remains static. Setup reviewed: only drawing changes; restart desktop mode to
  load them. No dependency, configuration or migration change is needed.

- Restyled only the native island's outer shell after the Joly UI Liquid Metal
  Button reference: black center, narrow chrome frame, flowing silver/slate
  reflections and a pointer-driven white glint. Compact, listening and expanded
  views share the finish. Reduced motion fixes the reflections in place; inner
  liquid-glass controls and spotlight tiles are retained. Setup reviewed/updated:
  restart desktop mode; no shader/npm package, setting, account or data migration.
  Native previews are synthetic; microphone/provider checks remain manual.

- Fixed Open workspace leaving a minimized dashboard minimized. The island and
  tray now restore the existing dashboard, and construction failures are logged
  and shown in the island instead of failing silently. Added button-driven first
  open, minimized/closed-window reopening and failed-open retry checks. Setup
  reviewed/updated: quit and restart through Start-ZENO.cmd; launch the GUI with
  normal window visibility. No dependencies, settings or data migration.

- Added the supplied GlowCard/spotlight-card treatment to the native Dynamic
  Island shell, live voice card and controls. One existing pointer timer drives
  a soft radial wash, colored edge bloom and white hotspot; hue follows horizontal
  screen position. Reduced motion disables the spotlight, disabled controls stay
  quiet, and microphone/approval/focus behavior is retained. Setup reviewed:
  restart desktop mode; no dependencies, configuration, accounts or migration.
  Added synthetic native spotlight previews; live hardware/provider checks remain
  manual.

- Applied the supplied LiquidButton glass treatment throughout ZENO's workspace,
  activity, settings, sign-in/approval dialogs, audit page, native tray and island.
  Shared web styling adds frosted layers, inset reflections, focus rings and
  bounded hover refraction; original Qt painting gives native controls matching
  reflective edges. Text remains unfiltered, reduced motion disables press/hover
  motion, and mobile navigation/settings adapt to narrow widths. Setup reviewed:
  restart desktop mode and refresh browser pages; no npm runtime, dependency,
  account, configuration or data migration. Hardware/provider checks stay manual.

- Restyled the native island with an Apple-inspired black pill, soft eased
  expansion, an aurora orb, rounded action tiles and a compact 360px listening
  view. Adapted the Dynamic Island patterns found on 21st.dev into original Qt
  painting; no React source, remote assets or new dependencies are shipped.
  Waveforms use measured capture levels and reduced motion keeps them static.
  Existing approvals, commands, focus rules and dashboard routing are retained.
  Setup reviewed and updated: restart desktop mode; no account, configuration or
  data migration. Added reproducible synthetic native previews; live hardware
  and provider checks remain manual.

- Added local Ollama reasoning and opt-in free-tier Gemini-to-local routing.
  Cloud calls default off; an existing key alone no longer enables them. Free
  cloud requires explicit confirmation of a billing-disabled Free-tier project,
  allows only reviewed Flash models and excludes hosted paid tools/cache options.
  Quota/auth failures fall back locally without retries. Local text, structured
  routing and planning preserve action validation; local text models cannot see
  screenshots. Added local runtime startup, diagnostics and a text-only smoke
  command. Local speech defaults to SAPI/faster-whisper without online fallback.
  External coding now requires separate CODING_ALLOW_EXTERNAL opt-in; it is not
  covered by the free-tier routing policy.
  Setup updated for Ollama/model downloads, speech dependencies, model storage,
  deadlines, account/privacy checks and explicit existing-.env migration.
  Live cloud billing/quota and hardware voice checks remain manual; no release
  or licensing decision is made.

- Replaced the microphone-active overlay with a reference-inspired slim black
  listening island, left-aligned label, cyan glow and level-reactive bars.
  Removed screen-edge lighting; click the listening island for controls, while
  approvals remain automatic. Reduced motion keeps capture feedback static.
  Setup and desktop guides updated: restart desktop mode; no new dependencies,
  settings, accounts or migration. Live microphone/provider checks remain manual.


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


- Added Aurora's reference-inspired Edge light style: dark desktop, animated
  perimeter glow, stacked floating lyrics, subtle clock and compact song footer.
  The mini-overlay defaults to transparent. Timed words retain their actual
  timestamps across visual rows; reduced motion disables drifting/pulsing. Select
  Edge light once on upgrade, retaining older styles and per-song presets. Setup
  reviewed/updated; restart required, no new dependencies or ZENO migration.

- Fixed Aurora desktop ambience covering icons: host its window below Explorer's
  icon layer, supporting classic WorkerW and Windows 11 raised desktops. Invalid
  layouts hide the canvas; no icon/wallpaper settings or Explorer restarts required.
  Restart Aurora to replace the old overlay. New-song lookups now survive cooldowns
  and automatically retry transient failures with capped backoff. Equivalent
  recordings on different album releases are selected automatically. Setup and
  diagnostics updated; no new dependencies, credentials or ZENO migration.

- Fixed Aurora lyric lookup for direct endpoint failures with one bounded search
  fallback. Accept up to five seconds of duration difference while retaining title,
  artist and album checks. The reported Spotify recording had available lyrics but
  a four-second provider duration mismatch and a direct endpoint 503.
  Added a shared click-through desktop ambience canvas, cover artwork, brighter
  artwork palettes and late-artwork retries. Player choice and desktop visibility
  persist; `--desktop` and `--player` are documented in setup. No wallpaper, startup
  or ZENO settings are changed by installation. Provider availability still varies.

- Extended standalone Aurora with opt-in LRCLIB lookup, strict recording matching,
  bounded/cancellable requests, cached/imported lyrics and per-song presets. Added
  enhanced-LRC word highlighting, smooth artwork palette transitions, draggable
  translucent overlay, source selection, tray and opt-in Windows startup. Added
  unsigned portable build and isolated smoke commands. Setup reviewed/updated for
  Aurora storage, privacy, startup and build paths; no ZENO migration or credentials
  changed. Spotify play/pause and YouTube Music in Chrome were checked; the latter
  loaded artwork and 47 timed lyric lines through the full app path. Fixed selected
  player preservation when recreating the reader and tolerated malformed cache origins;
  full player smoke tests and distribution rights remain pending. Secure Windows
  lock-screen replacement is unsupported, not marked complete.

- Added an independent Aurora desktop prototype under `standalone/aurora`, with
  silent sample lyrics, local LRC imports, artwork-derived colours, appearance
  controls, fullscreen and an optional Windows media-session reader. It has its
  own environment/launcher and no ZENO runtime dependency. Setup reviewed and
  linked to its guide; no ZENO environment variables or account migration needed.
  Online lyrics and partial player verification were subsequently added above;
  secure lock-screen rendering remains unsupported. This is not a product release.

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
