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
- Do a final pass for grammar, typos, punctuation, and especially Italian accents before closing the task.
- Verify spelling, accents, punctuation, and placeholders in emails, buttons, alerts, labels, and page copy.
- Use the correct project naming consistently: `MedLavDelta` is the platform name, while `Centro Delta` is the company name unless a page or document explicitly needs the legal entity wording.

## Dependency Hygiene

- Whenever a Python package is installed, upgraded, or added for project code or tests, update `requirements.txt` in the same change.
- Do not leave environment-only installs undocumented if the repository depends on them to run or test successfully.

## Dead Code Hygiene

- Periodically perform the task: `Delete all dead code. Use ruff and vulture.`

## Shared Behavioral Guidelines

These guidelines bias toward caution over speed. For trivial tasks, use judgment.

### 1. Think Before Coding

Don't assume. Don't hide confusion. Surface tradeoffs.

- State assumptions explicitly before implementing.
- If uncertain, ask.
- If multiple interpretations exist, present them instead of choosing silently.
- If a simpler approach exists, say so and push back when warranted.
- If something is unclear, stop, name what is confusing, and ask.

### 2. Simplicity First

Minimum code that solves the problem. Nothing speculative.

- No features beyond what was asked.
- No abstractions for single-use code.
- No flexibility or configurability that was not requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.
- Ask: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3. Surgical Changes

Touch only what you must. Clean up only your own mess.

- Don't improve adjacent code, comments, or formatting unless the task requires it.
- Don't refactor things that are not broken.
- Match the existing style, even if you would do it differently.
- Remove imports, variables, or functions that become unused because of your own changes.
- Do not remove pre-existing dead code unless asked.
- If you notice unrelated dead code, mention it instead of deleting it.
- Every changed line should trace directly to the user's request.

### 4. Goal-Driven Execution

Define success criteria. Loop until verified.

- Transform requests into verifiable goals before implementing.
- "Add validation" means writing tests for invalid inputs and making them pass.
- "Fix the bug" means reproducing it with a test or concrete check, then making that pass.
- "Refactor X" means ensuring behavior is verified before and after.
- For multi-step tasks, state a brief plan where each step includes how it will be verified.
- Strong success criteria enable independent execution. Weak criteria such as "make it work" usually need clarification.

### 5. Final Language Pass

Before closing any task that adds or changes user-facing text, do a final pass for grammar, spelling, punctuation, and typos.

- Pay special attention to Italian accents and apostrophes.
- Do not omit required accents in words such as `è`, `à`, `ì`, `ò`, and `ù` when they are correct in the target text.
- Re-read labels, alerts, emails, buttons, placeholders, table headings, and validation messages before closing the task.
