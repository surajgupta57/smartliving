# Mobile usability review

Reviewed 15 October 2026 against the local Smart Living application. Primary browser
review used the local MySQL catalogue on port 8027. Widths checked: 320, 390, 768
and 1280 CSS pixels. This was desktop-browser responsive testing, not an iPhone,
Android device or production-hosting acceptance test.

## Findings and corrections

| Finding | Correction |
|---|---|
| Product gallery intrinsic width caused page overflow at 390px. | Allow product grid children to shrink, constrain the single-column track, and wrap long product/specification text. Gallery thumbnails keep their own horizontal scrolling. |
| Small menu and refinement controls were difficult to tap; some inputs used 13px text. | Larger touch targets and 16px text in mobile form controls; telephone keyboard hint for phone entry. Real iOS keyboard/zoom behaviour remains a device check. |
| Long filters came before all results on mobile; at 768px the sidebar squeezed product cards. | Collapsible filters through 800px, with a single main layout column. Desktop filters remain visible. Without JavaScript, the filter form remains visible and usable. |
| Expanding the menu did not update the reserved header height. | Recalculate the header space after menu open/close to avoid covering page content. |
| Invalid submissions displayed scattered field errors without moving focus. | Focus a linked error summary and preserve submitted values and the quote shortlist. |
| Footer navigation targets were tightly packed. | Space links, provide an accessible Footer navigation label, and make configured phone/email contacts actionable. |

## Verified interactions

- Mobile menu opens; all existing public navigation links remain available.
- Header search for T1C returns the expected sensor and opens its product page.
- Live catalogue search for T1C returns one matching product.
- Combined CCTV category, IP/network technology and CP PLUS brand filters return
  five matching products; native Apply filters submission works.
- Product pages fit at 320px and 390px without whole-page horizontal overflow.
- Quote addition preserves a selected quantity of two in the shortlist.
- Empty quote submission focuses the error summary, links to required fields and
  preserves the shortlist. Phone input renders as tel with 16px mobile text.
- Site-survey form fits at 320px and displays the IST/preferred-time explanation.
- Footer survey, privacy and terms links open their expected pages.
- At 768px the catalogue uses the main column and collapsed filters. At 1280px
  the sidebar and product columns remain visible without page overflow.
- Separate Django-client validation on local MySQL successfully submitted a quote,
  rendered the confirmation, retained quantity two and cleared the session shortlist.
  All test database changes were rolled back; enquiry count was unchanged.
- WhatsApp URL rendering was checked with a mocked test number. No message was sent.

## Launch items still pending

- Contact details are now configured and verified in local MySQL: WhatsApp and phone
  +918668329719, email ssepadrauna@gmail.com. WhatsApp is enabled.
  Transfer these settings to production and verify the app handoff after deployment.
- Publish accurate service areas, warranty/installation scope and project content.
  Existing privacy/terms pages contain short starter text and need business review.
- Repeat on actual iOS Safari and Android Chrome, including keyboard-open search,
  date/time selection, touch scrolling and the WhatsApp app handoff.
- Repeat on production after deployment, including static/media delivery and hosting latency.

## Validation

51 catalogue/lead tests passed on an isolated SQLite test database. Django system
checks and migration-drift checks passed. Static collection succeeded. The MySQL
submission check above used a transaction rollback rather than creating a MySQL
test database. No claim is made that this turn reran the full suite on MySQL.

Screenshot: [mobile catalogue](mobile-review-catalogue.jpg).
