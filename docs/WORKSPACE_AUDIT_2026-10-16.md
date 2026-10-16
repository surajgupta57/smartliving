# Workspace audit — 16 October 2026

## Result

All workspace routes and their existing workflows were checked. Functional regression checks pass after the fixes below. This is local verification, not production deployment acceptance.

- Full project suite: **92 tests passed**, using an isolated SQLite test database.
- Lead/workspace coverage: **40 tests passed**, including 21 new audit tests.
- Django system check: passed.
- Migration drift: none.
- Static discovery: workspace CSS and quote-line JavaScript found.
- Configured MySQL: authenticated GET views returned 200 inside an explicitly read-only transaction, rolled back at completion. No real enquiry, quotation, session or permission changes were submitted.
- Browser: isolated SQLite audit database, fictitious customer records, local server on 127.0.0.1:8001. Working paths were exercised at 390px and 1280px viewport widths. No page-wide horizontal overflow; wide tables and pipeline columns scroll inside their containers. No browser console errors were observed in the final check.

## Page-by-page checks

| Page / feature | Checks completed | Result |
| --- | --- | --- |
| Overview `/workspace/` | Total/open/won counts, overdue excludes closed leads, stage links, recent enquiries, quotation permission check, follow-ups through the end of tomorrow | Pass |
| Lead management `/workspace/enquiries/` | Name/phone/email search, priority/source/owner filters, combined filters, open/unassigned summary links, sort order, invalid filter/page handling, pagination | Pass |
| Sales pipeline `?view=board` | Stage placement, counts, filter preservation, list/board switching, empty columns, maximum 20 cards per column with view-all link | Pass |
| Assigned to me `?mine=1` | Shows current user's assignments; combines with other filters | Pass |
| Follow-ups due `?due=1` | Only due active leads; closed enquiries excluded; overdue text and scheduling | Pass |
| Site surveys queue `?surveys=1` | Filters survey-source enquiries and opens connected visits | Pass |
| New enquiry `/workspace/enquiries/new/` | Browser creation, required fields, phone validation, invalid/empty POST, assignment to creator, source and creation activity; no fabricated website consent | Pass |
| Enquiry detail `/workspace/enquiries/<id>/` | Customer/project information, assignment, status, priority, IST follow-up, notes, activity recording, viewer write denial, inactive owner rejection, linked surveys and quotations | Pass |
| New quotation `/workspace/enquiries/<id>/quotation/` | Date default, dynamic Add line, unused rows, required lines, numeric validation, tax totals, 50-line limit, atomic draft creation, add-only permission redirect | Pass |
| Edit draft `/workspace/quotations/<id>/edit/` | Saved date, adding/removing lines, recalculated totals, foreign quotation line protection, sent quotations frozen | Pass |
| Quotation `/workspace/quotations/<id>/` | Customer/company snapshots, reference, prices, subtotal, rounded tax, total, status display, permission checks | Pass |
| Quotation status `/workspace/quotations/<id>/status/` | POST only, CSRF required, draft→sent→accepted/declined, invalid transitions rejected, terminal states protected, activity recording | Pass |
| Manage survey `/workspace/enquiries/<id>/surveys/<id>/` | Matching lead required, permission checks, future appointment validation, browser scheduling, notes, activity history; existing past appointment can retain its time during note updates | Pass |
| Administration entry `/admin/` | Opens successfully for audit staff; permitted lead models listed; quotation and activity standalone admins are read-only by existing design | Entry checked; not a complete Django admin audit |
| Print / save PDF | Actual Chrome PDF output from the quotation template: 2-line sample on one A4 page; 50-line sample on five A4 pages; every page visually inspected; all rows, totals, repeated table headings and page numbers checked | Pass |

## Issues fixed

1. Empty POST requests now bind forms, display validation errors and avoid silent unbound re-renders.
2. Quotation edit date inputs now use ISO format, retaining the saved valid-until date.
3. Overview follow-ups include the entire next calendar day in IST, rather than only the next 24 hours.
4. All-leads stage tab clears only the stage and preserves the other filter/view choices.
5. Non-ASCII numeric owner parameters no longer reach integer database lookups.
6. Staff with add-quotation permission but without view-quotation permission return to the accessible enquiry page after creation.
7. Existing scheduled surveys can retain a past appointment time while staff update notes; newly scheduled past times remain invalid.
8. Quotation hidden form fields sit inside table cells; visible line fields have accessible names; submitted formsets are bounded to 50 rows.
9. Authenticated workspace responses use no-store cache headers.
10. Sales-role seed definitions include survey viewing for viewers and survey updating for operators. **Update: seed command applied to configured MySQL. Sales viewer now includes view_consultation; Sales operator includes view_consultation and change_consultation. Both groups have zero members; no user memberships changed.**
11. Print layout removes the website header spacer to avoid unnecessary blank space.
12. Follow-up fields explain IST and that saving a date does not send an automatic notification.

## Boundaries and manual operations

- Mutation workflows and browser fixtures used SQLite; MySQL mutation tests were not run because the configured application user cannot create the test database. MySQL read-only page rendering passed.
- No production DNS/TLS/hosting, email, SMS or WhatsApp delivery was tested.
- Follow-ups populate the queue; automated customer reminders are not implemented.
- Quotation progress and enquiry sales stage remain separate manual controls. Sending or accepting a quotation does not automatically change the enquiry's stage.
- Pipeline stage changes use the enquiry's Next action form; drag-and-drop is not implemented.
- Sales-role definitions have now been applied in MySQL following user authorization. Both groups currently have zero members; users still need an appropriate group assignment and staff status to use these permissions.
- Actual Chrome-generated A4 PDFs have now passed visual and text checks. Physical-printer behavior and other browser print engines were not tested. PDF sample generation used fictitious customers and an in-memory SQLite database; no real quotation was created or changed.

## PDF and role completion

Completed following the request to implement the two remaining items.

- Applied seed_sales_roles to configured MySQL and verified the permissions stored on both named groups.
- Improved A4 print CSS: stable two-column headings, fixed table column widths, repeated table headings, intact rows/totals, hidden website controls, and Page N of M footers.
- Generated and inspected output/pdf/quotation-sample.pdf (one page) and output/pdf/quotation-multipage-sample.pdf (five pages, 50 lines).
- Verified line numbering and totals: INR 5,826.84 and INR 145,671.00 respectively; all items present once; no website navigation or internal workflow controls in the PDFs.
- Re-ran all 40 lead/workspace tests successfully after these changes.
- Browser rendering used a disposable local profile and local HTML; sample PDFs contain only fictitious data. The local renderer required its per-process sandbox to be disabled in this environment. No installed browser settings or application security settings were changed.
