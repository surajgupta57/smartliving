# Security maintenance and deployment

Local validation on 16 October 2026: all 151 application tests passed using an
isolated SQLite database. The configured MySQL user cannot create a test database;
the new migration was applied locally and an eleven-request MySQL throttle smoke
check passed inside a rolled-back transaction. Django checks and migration drift
checks passed. Installed Django is 5.2.18. The dependency audit identified pip 25.2
advisories; the local installer was upgraded to 26.2. Git tracking/history review
was blocked by the parent repository's ownership check, so historical secret
exposure has not been ruled out. No live hosting configuration was modified.

Public contact, quotation, product-enquiry and survey POSTs share a limit of 10
attempts per five-minute window per client address. Admin login POSTs have a
separate limit of 20. Both valid and invalid submissions count. Normal browsing
and staff workspace operations are unaffected. A blocked request returns HTTP
429 with Retry-After and no-store headers. Database counters coordinate workers,
store keyed hashes rather than IP addresses, and expire during later requests.
Fixed windows can allow twice the limit across a window boundary.

Deploy the core migration with `python manage.py migrate` before serving traffic
with the new middleware. Back up the database first as described in the
production deployment guide. No new package is required.

Limits use REMOTE_ADDR, never arbitrary forwarded headers. On a reverse proxy,
the host must securely supply the real client address to the application;
otherwise customers can share a limit. Verify this on the actual hosting stack.
These application limits supplement host-level traffic protection; they do not
stop distributed attacks or traffic that overwhelms the web server.

Use config.production and run `python manage.py production_check` on the host.
Existing production settings enforce HTTPS, secure cookies, exact hosts, private
document storage and DEBUG=False. Keep secrets outside the public document root,
deny web access to dotfiles, source, backups and private var directories, disable
script execution in public media, and verify those rules over HTTPS. Keep backups
private and test restoring them. No hosting changes are implied by local checks.

Keep requirements patched, run a dependency vulnerability scan in the deployment
environment, and use unique staff passwords with minimum permissions. Before
launch, verify real login, enquiry, quotation, private-download and logout flows,
including the rate-limit client address behavior. Live TLS, proxy behavior,
server file rules, backups and historical secret exposure require host/repository
access and are not established by local regression tests.
