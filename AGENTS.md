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

## Lists And Tables

- Every new user-facing list or table must include a search bar when the content is large enough to browse.
- Every new user-facing list or table must support sortable columns with the classic ascending and descending toggle on the most relevant fields.
- Search and sorting must preserve existing filters when possible.
- Search bars, filters, and sorting controls must remain mobile friendly and must not introduce horizontal overflow outside intentionally scrollable tables.
- When extending an existing list, keep search and sort behavior consistent with the other dashboard lists already present in the project.

## Copy Review

- Double-check every new user-facing text before closing the task.
- Verify spelling, accents, punctuation, and placeholders in emails, buttons, alerts, labels, and page copy.
- Use the correct project naming consistently: `MedLavDelta` is the platform name, while `Centro Delta` is the company name unless a page or document explicitly needs the legal entity wording.

## Dependency Hygiene

- Whenever a Python package is installed, upgraded, or added for project code or tests, update `requirements.txt` in the same change.
- Do not leave environment-only installs undocumented if the repository depends on them to run or test successfully.
