# Notch interface visual review

Reference: the user-selected Glance reel at
https://www.instagram.com/reel/DfCe-PAs6jH/ . Playback frames inspected in the
in-app browser showed the black notch, compact dark utility surfaces and colored
edge lighting. Instagram subsequently stopped exposing playable video. The exact
microphone transition and its timing could not be verified.

Scope: adaptation of the visual direction to ZENO's existing native Windows
island and separate desktop/web dashboard. Existing command, approval, telemetry
and preferences behavior is retained. No Glance integrations are implied.

## Captures

- [Listening island](island-listening.png): native Qt render using simulated state.
- [Motion preview](island-motion-preview.gif): simulated levels through the actual
  island renderer; no audio capture.
- [Dashboard](notch-dashboard.png): embedded shared HTML/CSS/JS rendered at a
  scaled preview viewport. DOM reported width 1142, scroll width 1121; no
  horizontal overflow. Voice card and active capture class were present.

## Review

- Black resting surfaces, restrained borders, compact controls and color focused
  in microphone feedback follow the observed reference direction.
- Dashboard stays separate from island hover; preferences and existing task
  controls remain available.
- Meter/rim/screen light follow actual capture-open/close events in production.
  Tests verify no light on open failure, correct stream/light closure order,
  transparent input flags and Stop cleanup. Reduced motion retains static
  capture feedback with no animation timer.
- 29 focused desktop/dashboard tests passed; documentation and JavaScript syntax
  checks passed. No live microphone or provider check was performed in this UI
  redesign. Gemini availability remains unverified.

Final result: passed for the implemented visual adaptation and tested state
handling. Exact reference-animation fidelity remains unverified because the full
microphone sequence could not be inspected.
