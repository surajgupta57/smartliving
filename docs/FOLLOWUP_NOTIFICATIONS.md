# In-portal follow-up notifications

Open **Workspace → Notifications** (`/workspace/notifications/`).

- The sidebar badge counts your assigned open leads with follow-ups overdue or scheduled before the end of today in IST.
- **My follow-ups** is the default view. **Unassigned** and **All team follow-ups** provide the corresponding team queues, under the same staff + view-enquiry permission as the existing workspace.
- **Due now / overdue** includes timestamps at or before now. **Later today** contains future times before the next IST midnight. Tomorrow's follow-ups do not appear yet.
- Won/lost leads and leads without a follow-up date are excluded.
- Open **Record follow-up** to use the existing Next action form. Record a note, then clear or reschedule the follow-up. Changes continue to use existing activity logging. Read-only viewers see **View enquiry** instead.
- The badge checks for updated counts every minute while the portal is visible, and when the tab regains focus. No form is reloaded. Use **Refresh reminders** for an updated list.
- Counts represent outstanding work, not unread messages. Opening a reminder does not dismiss it. Closing a lead, clearing/rescheduling its date, or reassigning it updates the appropriate queue automatically.
- No scheduler, task worker, notification table or database migration is required. The portal reads the current saved follow-up dates. No email, SMS, WhatsApp or desktop push message is sent.

## Validation (16 October 2026)

- 112 Django project tests passed using isolated SQLite, including 16 new reminder tests.
- Three JavaScript tests passed: count/accessible-label updates, hidden-tab and expired-session behavior, offline/invalid-payload handling.
- Browser: verified personal queue, removal after clearing a follow-up, unassigned queue, badge changes, IST labels and mobile width using fictitious customers in a separate disposable database.
- Read-only MySQL checks passed for personal, unassigned and all-team pages and the count endpoint.
- Static assets collected locally; system checks and migration-drift checks passed.
- Real customer records were not changed by validation. Production deployment and external notification delivery were not tested.

Repeat checks:

```powershell
$env:DJANGO_DB_ENGINE='sqlite'
.\.venv\Scripts\python.exe manage.py test --noinput
node --test scripts/test_workspace_reminders.cjs
```

Run the test database override only for the test command/session; normal application settings continue to use the configured database.
