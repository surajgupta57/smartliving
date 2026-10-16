# Customer activity history

Open an enquiry from Workspace → Lead management.

## Available workflow

- The header shows the owner, current follow-up and last logged call/meeting in IST.
- Record a completed phone call, meeting or internal note using **Record customer activity**.
- Add an optional outcome or next step, and required notes (up to 4,000 characters).
- An optional future follow-up updates the existing enquiry reminder date. Leaving it blank preserves the current follow-up.
- Logging a contact preserves the enquiry's stage, priority and owner. Change those separately in **Next action** when needed.
- Closed enquiries accept historical notes, but must be reopened before scheduling another follow-up.
- The history groups calls, meetings, notes, workflow updates, quotation activity and survey activity. Filter by type; longer histories show 20 entries per page.
- Customer details, survey records and quotations remain linked on the same enquiry page.

## Access and data boundaries

Staff need `leads.view_enquiry` to view the page and `leads.change_enquiry` to record contact activity. These match the existing sales workflow permissions. Recording activity does not require granting direct audit-record administration access.

Quotation and survey sections and their timeline events respect their existing viewing permissions. Activity creation is POST-only, CSRF protected, and records the current authenticated staff member. Old entries remain unchanged; refreshes do not create history events.

History belongs to the selected enquiry. Separate enquiries are not merged by shared phone number or email address. The form records staff notes; it does not place a phone call, invite meeting attendees or send a message.

## Validation — 16 October 2026

- Full suite: 126 tests passed on isolated SQLite.
- Fourteen new customer-history tests cover activity types, workflow preservation, optional follow-ups, IST parsing, closed enquiries, filtering, pagination, CSRF, staff permissions, content escaping and record separation.
- Browser: recorded a fictitious call, verified its history entry and follow-up notification, exercised Calls filtering, and checked the mobile form and jump links at 390px without page-wide overflow.
- Configured MySQL: read-only detail/history-filter checks passed; no real customer activity was added during verification.
- No database migration needed. Static assets collected locally.
