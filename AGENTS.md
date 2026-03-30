# Project Instructions

## Always Mobile Friendly

Every UI change in this repository must remain mobile friendly by default.

Apply these rules on every frontend edit:

- Keep layouts usable on small screens, especially around `360px` width and common tablet widths.
- Prefer responsive grids that collapse to a single column on narrow screens.
- Avoid introducing horizontal overflow for forms, cards, headers, and action bars.
- If a wide data table is necessary, wrap it in a horizontal scroll container instead of letting the page break.
- On mobile, action buttons should stack or expand to full width when space is tight.
- Touch targets must remain easy to tap and text must stay readable without zooming.
- Preserve existing responsive breakpoints and patterns already used in `templates/base.html`.
- When adding new UI, include the responsive CSS in the same change instead of treating it as a later refinement.

## Working Rule

Before closing a UI task, quickly verify:

- header and actions do not collide on mobile;
- forms collapse cleanly;
- tables remain navigable;
- no new element forces the viewport wider than the screen, except intentionally scrollable tables.
