# Mobile and tablet workspace

The CRM workspace now uses responsive layouts across its overview, lead queue, pipeline, notifications, customer history, staff enquiry forms, surveys and quotations.

- At widths up to 1100px, the workspace menu collapses behind **Sales menu**. Reminders remain directly accessible. Navigation remains visible if JavaScript is unavailable.
- The public header becomes compact within the workspace while keeping product search and the website menu available.
- Phone lead tables become labelled customer cards with a full-width Open action. Table headers remain available to assistive technology.
- Phone quotation editing uses stacked line cards, including dynamically added rows and labelled Remove controls.
- Tablet and phone forms use at least 16px input text with controls at least 44px high. Filters and panels reflow; long customer names, emails and notes wrap.
- Pipeline columns can be swiped horizontally within the board. Read-only quotation tables retain their columns and scroll within their container.
- Desktop layouts remain available above the compact breakpoint. New responsive rules are screen-only, preserving A4 print styles.
- The sales menu supports keyboard navigation, Escape to close, and focus recovery when a viewport change hides a focused navigation link.

## Verification — 16 October 2026

Browser checks used fictitious records in a disposable SQLite audit database. Ten workspace pages were checked at each of 320px, 390px, 768px, 1024px and 1280px: 50 page/size combinations, no page-wide horizontal overflow. All visible phone/tablet form fields had text of at least 16px. The menu, Escape key, mobile lead opening, quotation Add line and saving were exercised.

The mobile save check exposed an existing formset issue: a complete later quotation line was rejected when the first new line was unused. New rows can now be left blank in any position; at least one complete line is still required. Regression tests cover both cases, as well as existing line/tax validation and quotation protection.

Repeat JavaScript checks with:

```powershell
node --test scripts/test_workspace_layout.cjs scripts/test_workspace_reminders.cjs
```

No production hosting or physical-device testing was performed. Browser viewport checks cover layout and interaction at the stated sizes.
