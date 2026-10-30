# OriginKit-inspired native island

## Sources and adaptation

- [Ribbon Glow](https://www.originkit.dev/components/ribbon-glow): cyan/violet
  ribbons, dark ground, eased pointer presence and low-key drift.
- [Glass Icon](https://www.originkit.dev/components/glass-icon): reflective edge
  treatment and a small glass-like brand mark.
- [Cursor Ring Field](https://www.originkit.dev/components/cursor-ring-field):
  a pointer-following band that brightens scattered points.

The component descriptions and public preview images were inspected. Browser
preview capture was unreliable, so the public component poster images supplied
visual grounding. Those reference images remain in ignored scratch files; they
are not shipped in ZENO. This is an original native Qt adaptation, not a WebGL
shader port or imported OriginKit source. No OriginKit runtime or service is used.
The bundled Lucide 0.468.0 icons retain their upstream ISC/Feather license in
`desktop/assets/icons/LICENSE-lucide`. ZENO's own licensing remains undecided.

## Implemented layout

The compact pill has a reflective mark, current status and Talk/Stop/Retry control.
Hover opens a ribbon-backed live voice card, response area, two quick-action
cards (Type a request / Open workspace), and a Preferences/Minimize footer.
The input and approval rows expand the panel to fit their contents, preserving
scrollable approval text. The full dashboard is still a separate window.

The ambient field and button highlights follow cursor movement. Hover reversal
starts from the current dimensions rather than snapping. Reduced motion stops
ribbon drift, pointer-field highlights and hover interpolation. Microphone rim
and screen-edge lighting retain the stream-open/close lifecycle from the previous
update. Icons and effects load locally; no extra package or configuration is used.

## Visual review

- [Compact](island-compact.png) and [expanded](island-expanded.png): actual native
  Qt renders, showing final icon labels, spacing, card hierarchy and footer.
- [Motion](island-originkit-motion.gif): simulated level/cursor input through the
  native renderer. No microphone or model request is made for these previews.
- Reference comparison: adapted the dark ground and cyan/violet ribbons while
  reducing their intensity behind readable controls. The glass reference becomes
  a small vector UI mark; the cursor field uses fewer particles to suit the
  island. This is visual inspiration, not a pixel-for-pixel match to a source demo.
- Found and fixed: footer Preferences label truncation; added text-based button
  sizing. Composer/approval rows now grow the panel and retain visible actions.
- Desktop regression checks cover hover reversal, pointer-away collapse,
  request-bound approvals, text submission, focus flags, actual mic lifecycle,
  reduced-motion lighting and adaptive layout.

Final result: passed for the native design adaptation and tested controls.
Live microphone recognition and AI/provider availability remain manual checks.
ZENO was left closed after this change.
