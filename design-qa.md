# Microphone island visual check

final result: passed

Scope: reference-inspired replacement of the native Qt microphone-active view.
Source: user-attached laptop photo, focusing on the dark Listening bar inside
the screen; the green annotation, bezel and photographed surroundings are excluded.
Implementation: [listening capture](docs/island-cyan-listening.png), 600 by 68 logical pixels,
rendered with Qt offscreen and simulated microphone capture/level events.

Compared the source and rendered native component: slim horizontal silhouette,
dark surface, bold white left-aligned Listening label, generous empty center,
and cyan bars/glow contained at the right. No photo textures or image assets are
part of this UI. Width is capped to the screen's available space. This is an
inspired adaptation, not a pixel-exact recreation of the perspective photograph.

Initial capture showed missing font glyphs in Qt's offscreen backend. Re-rendered
with the installed Windows Segoe UI regular/bold fonts registered in the capture
process; the final capture has readable text. No application font change needed.
Typography, spacing, color, content and edge quality checked after re-rendering.
No outstanding P0/P1/P2 visual findings in the final listening capture.

Verification: 28 desktop tests passed; documentation checker passed. Tests cover
compact capture, hover behavior, control access, approvals, reduced motion and
capture closure. Native hardware, real speech and provider checks remain manual.
Browser/prototype hosting steps do not apply to this existing PySide6 desktop UI.
