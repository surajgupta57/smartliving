# Production readiness evidence

Prepared on 16 October 2026 for the independent Smart Living cPanel Python App / Passenger deployment at https://smartliving.seas-india.com.

## Application work completed

- Strict production settings require private credentials, exact hosts, HTTPS, secure cookies, MySQL and separate public/private storage. Proxy header trust is explicitly configured by the hosting operator.
- Production dependencies are pinned; Django was upgraded to 5.2.18. The production package audit reported no known vulnerabilities at verification time.
- Product documents now use private storage with permission-checked downloads. All 101 existing local document paths were copied, verified and removed from public media. Staff documents require the appropriate staff permission; public documents require an active, published product.
- Added health probes, database-independent error pages, production preflight, a private backup command, clean release builder, Passenger template and read-only HTTPS smoke checker.
- Saved the supplied business address in the existing local Site settings record: Padrauna, Kushinagar, Uttar Pradesh, 274304. This record must be transferred with business data to a new server database.

## Verification completed locally

- All 155 Django tests passed, including production configuration, private document authorization and backup/release tooling. Tests ran against SQLite on local Windows/Python 3.14; this does not establish Linux interpreter or hosting compatibility.
- Passenger entry-point import and full production preflight passed against the configured local MySQL database with an ephemeral production verification secret and separate collected static files.
- Production manifest collection and configuration checks passed. HSTS warnings W005/W021 are deliberately retained because child-subdomain coverage and browser preload are disabled.
- A real local MySQL backup completed. SHA256 checks and media/private-document archive validation passed. The SQL contains schema/data without CREATE DATABASE or USE directives.
- Backup files remain private under var/private_backups and are excluded from releases. The backup predates the final business-address edit; take another backup before deployment or further production changes.

## Required on cPanel before accepting live traffic

Follow PRODUCTION_LAUNCH.md in this directory. These actions have not been performed or verified remotely:

1. Install the pinned packages in the hosting Python virtualenv and configure the real, separate Smart Living MySQL credentials privately. The local .env.production file still contains hosting database placeholders; never publish it.
2. Transfer the intended business database, public media and private documents; run migrations, secure_product_documents, rebuild_product_search and collectstatic as documented. The source ZIP deliberately contains no business data.
3. Register Passenger, configure static/media serving and private-path protection, restart the app, and verify DNS, valid TLS, HTTPS redirects and the host's trusted proxy behavior.
4. Run the full production_check and HTTPS smoke tool against the deployed app. Verify a genuine enquiry, staff login, role restrictions, follow-up, quotation PDF and document access in desktop/mobile browsers.
5. Configure off-host backups, cron, logging and host abuse controls. Rehearse restoring the backup into a separate database and private storage before considering recovery verified. An intact archive alone does not prove a successful restore.

The release is prepared for deployment; the live service has not been certified by local checks. Do not reuse SEAS application directories, database or accounts.
