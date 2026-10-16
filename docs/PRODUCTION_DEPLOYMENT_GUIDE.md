# Smart Living production deployment guide

> **Current hosting instructions (16 October 2026):** follow [the working cPanel configuration](CPANEL_WORKING_CONFIGURATION.md). The owner reported the site working after replacing the recursive Passenger loader and using real public static/media directories. The older symlink layout below is not the layout to reapply on this account. The updated deployer supports these public roots; follow [the automation setup](DEPLOYMENT_AUTOMATION.md) before its first run.

For the GoDaddy Economy account with **Setup Python App** confirmed in this chat,
follow [GODADDY_CPANEL_LAUNCH.md](GODADDY_CPANEL_LAUNCH.md). It includes the current
catalogue/CMS transfer and private PDF layout. Use one consistent execution path.

**Updated 16 October 2026:** use [PRODUCTION_LAUNCH.md](PRODUCTION_LAUNCH.md) as the current execution checklist. It covers the strict production profile, private document relocation, manifest assets, preflight, health probes and backup command. The detailed hosting/rollback reference below remains supplemental.

Target: **https://smartliving.seas-india.com**. Prepared 15 October 2026 from this checkout and the SEAS `docs/PRODUCTION_COMMANDS_GUIDE.md`.

This is a first-deployment and ongoing-operation runbook for Linux cPanel hosting with Passenger and MySQL. Hosting account name, actual Python environment path, DNS address, proxy behavior and installed server packages must be confirmed on your host. The paths below define a proposed Smart Living layout; they are not a claim about an existing server. Smart Living remains independent of the SEAS application, database, users and document root.

**Run one step at a time. Stop on errors.** Server command blocks use Bash in cPanel Terminal, not Windows PowerShell. Never use Django `runserver` for public production traffic.

## 1. Confirm hosting prerequisites

In cPanel or with hosting support, confirm:

1. A Python WSGI/Passenger application feature: usually **Setup Python App** (CloudLinux) or **Application Manager**. These interfaces differ; use the actual generated virtualenv and restart controls on your host.
2. Python 3.11 or 3.12, with an isolated environment for Smart Living.
3. MySQL 8, a separate database and database-scoped user, `utf8mb4`, and permission to run schema migrations. Confirm the host's exact database version is supported by the installed Django version.
4. `mysqlclient` can be installed. If compilation fails, support must provide the MySQL client development libraries/build tools or a compatible package. Do not substitute a different database driver silently.
5. HTTPS certificate issuance, Terminal/SSH access, file upload, scheduled jobs, error logs, sufficient disk/inodes and a restorable backup facility.
6. Apache can serve `/static/` and `/media/` from the public document root, including approved symlinks if using this layout. Public uploads must never execute as scripts.

Do not modify the SEAS domain, its application registration, `.htaccess`, virtualenv or database.

## 2. Choose and record the server paths

Recommended separation:

```text
/home/CPANEL_USER/
  apps/smartliving/
    current/                 application source, manage.py, config/, .env
      media -> ../shared/media
      staticfiles -> ../shared/staticfiles
      var -> ../shared/var
    passenger/passenger_wsgi.py
    shared/media/            persistent uploaded product images/documents
    shared/staticfiles/      collected public CSS/JS
    shared/var/              private import files
    backups/                 private database/media/config backups
    logs/                    private application logs
  public_html/smartliving/    document root for ONLY smartliving.seas-india.com
    .htaccess                generated Passenger configuration if used by host
    static -> /home/CPANEL_USER/apps/smartliving/shared/staticfiles
    media -> /home/CPANEL_USER/apps/smartliving/shared/media
```

The source and `.env` are outside `public_html`. No public symlinks to `current`, `var`, backups, source archives or database exports.

Run at the start of each server terminal session:

```bash
export ACCOUNT_ROOT="${HOME:?Cannot determine cPanel home}"
export APP_ROOT="$ACCOUNT_ROOT/apps/smartliving"
export RELEASE_ROOT="$APP_ROOT/current"
export PASSENGER_ROOT="$APP_ROOT/passenger"
export SHARED_ROOT="$APP_ROOT/shared"
export DOC_ROOT="$ACCOUNT_ROOT/public_html/smartliving"
umask 077
mkdir -p "$RELEASE_ROOT" "$PASSENGER_ROOT" "$SHARED_ROOT/media" "$SHARED_ROOT/staticfiles" "$SHARED_ROOT/var/private_imports" "$APP_ROOT/backups" "$APP_ROOT/logs" "$DOC_ROOT"
```

Keep these variables available for later commands. Use your host's real paths if it cannot support this layout. Do not change permissions recursively to 777; the application needs write access to media, private imports and collected static, while Apache needs traversal/read access to public assets. Ask support to apply the account's ownership/group model.

## 3. Create the subdomain and HTTPS

1. In **cPanel → Domains**, create `smartliving.seas-india.com` with its own document root `$HOME/public_html/smartliving`. Disable sharing another domain's root.
2. In the authoritative DNS provider, create an `A` record for `smartliving` pointing to the hosting IPv4 address supplied by the host. Add `AAAA` only if that host serves this app over IPv6. Remove conflicting records for the same name as needed; leave other SEAS records untouched.
3. In **SSL/TLS Status**, issue/install the certificate including this exact hostname. DNS must resolve appropriately for the host's validation method.
4. If using a CDN/proxy, ensure encrypted origin connections and a valid origin certificate; verify Django receives a trustworthy HTTPS indication before enabling redirects.
5. Check `nslookup smartliving.seas-india.com` and the certificate in a browser. For private pre-DNS testing, use a local hosts-file override to the server IP with the same hostname; do not broaden `ALLOWED_HOSTS` to `*`.

## 4. Upload a clean application release

Upload the project contents to `$RELEASE_ROOT`, so `manage.py` is directly inside `current/`. Include `apps/` and all migrations, `config/`, `templates/`, `static/`, requirements files and, if importing the catalogue, the complete `catalogue_seed/manufacturers/manifest.json` plus `assets/`.

Exclude `.venv/`, `.env`, `.git/`, `__pycache__/`, local databases, `var/`, logs, backup archives and generated `staticfiles/`. Transfer approved media separately in step 10. Inspect archive contents before uploading: the repository ignore rules do not exclude every local data file. Never upload a whole unreviewed project ZIP into the public document root.

Check:

```bash
ls -l "$RELEASE_ROOT/manage.py" "$RELEASE_ROOT/config/wsgi.py" "$RELEASE_ROOT/requirements-production.txt"
```

Connect persistence on a **new deployment only**, before creating uploads or collecting static:

```bash
ln -s "$SHARED_ROOT/media" "$RELEASE_ROOT/media"
ln -s "$SHARED_ROOT/staticfiles" "$RELEASE_ROOT/staticfiles"
ln -s "$SHARED_ROOT/var" "$RELEASE_ROOT/var"
```

If any destination already exists, stop and inspect it. Move/copy its approved contents into shared storage with a backup first, then replace that directory deliberately. Do not run recursive removal to make these commands succeed. On later updates preserve these links.

## 5. Register the Python application

In **Setup Python App** use:

| Field | Value |
|---|---|
| Python version | 3.11 or 3.12, matching your tested environment |
| Application root | `apps/smartliving/passenger` relative to account home |
| Application URL | `smartliving.seas-india.com`, path `/` |
| Startup file | `passenger_wsgi.py` |
| Entry point | `application` |
| Mode, if offered | Production |
| Passenger log, if offered | absolute `$HOME/apps/smartliving/logs/passenger.log` path |

For Application Manager use its equivalent registration workflow; if it cannot select a per-app interpreter, ask support to configure this application's Python. Do not change a server-wide interpreter affecting other apps.

Copy the exact environment activation command shown by the panel. Activate it, then set `VENV_BIN` from that environment:

```bash
# First run the exact activation command copied from YOUR panel.
export VENV_BIN="${VIRTUAL_ENV:?Activate the Smart Living virtualenv first}/bin"
"$VENV_BIN/python" --version
cd "$RELEASE_ROOT"
"$VENV_BIN/python" -m pip install -r requirements-production.txt
"$VENV_BIN/python" -m pip check
"$VENV_BIN/python" -c "import django, MySQLdb, PIL, import_export; print('Django', django.get_version(), 'MySQL driver and image/import packages available')"
```

Do not reuse the SEAS virtualenv. Requirements currently specify version ranges rather than a full lock; record the installed versions after acceptance and reproduce that tested set for subsequent releases:

```bash
"$VENV_BIN/python" -m pip freeze > "$APP_ROOT/backups/requirements-first-release.txt"
```

## 6. Create the production database and private settings

In **cPanel → MySQL Databases / Database Wizard**:

1. Create a new Smart Living database and a separate user with a generated password.
2. Assign that user privileges on this database only, including migration privileges. Copy the full cPanel-prefixed database/user names.
3. Record the actual host/port from support (usually `localhost:3306`). Local development port 3307 is not a production default.
4. Confirm the database uses `utf8mb4`. Use phpMyAdmin or support to set it before import if necessary.

Create `$RELEASE_ROOT/.env` using cPanel File Manager outside the public root. Enter real values privately:

```dotenv
DJANGO_ENV=production
DJANGO_SECRET_KEY=REPLACE_WITH_A_UNIQUE_RANDOM_SECRET
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=smartliving.seas-india.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://smartliving.seas-india.com
DJANGO_SECURE_SSL_REDIRECT=True
DJANGO_DB_ENGINE=mysql
DB_NAME=CPANEL_PREFIX_smartliving
DB_USER=CPANEL_PREFIX_smartliving_app
DB_PASSWORD='REPLACE_WITH_DATABASE_PASSWORD'
DB_HOST=localhost
DB_PORT=3306
```

Generate the secret in a trusted password manager or private local terminal with `python -c "import secrets; print(secrets.token_urlsafe(64))"`. Do not paste secrets into chat, screenshots, version control or public logs. Quote dotenv values containing special characters correctly; use the password exactly as issued.

```bash
chmod 600 "$RELEASE_ROOT/.env"
```

This project loads `BASE_DIR/.env` with `override=False`. Existing process/cPanel environment variables take precedence. Use one authoritative settings source or keep both synchronized; changing `.env` will not override stale panel variables. Do not `source .env` in Bash: dotenv syntax and shell syntax differ.

**Production gates:** select `config.production` or set `DJANGO_ENV=production`. The production profile refuses missing/placeholder secrets, missing database values, SQLite fallback and unsafe hosts. Local development retains its separate defaults. Verify effective settings without printing passwords:

```bash
cd "$RELEASE_ROOT"
"$VENV_BIN/python" manage.py shell -c "from django.conf import settings as s; from django.db import connection; assert not s.DEBUG; assert len(s.SECRET_KEY)>=50 and s.SECRET_KEY!='development-only-change-before-deployment'; assert s.DATABASES['default']['ENGINE']=='django.db.backends.mysql'; assert s.SECURE_SSL_REDIRECT; assert s.SESSION_COOKIE_SECURE and s.CSRF_COOKIE_SECURE; connection.ensure_connection(); print('Production flags and MySQL connection OK')"
```

## 7. Configure Passenger startup

Back up any generated startup file privately first. In `$PASSENGER_ROOT/passenger_wsgi.py` use:

```python
import os
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent / "current"
sys.path.insert(0, str(project_root))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.production")
from config.wsgi import application
```

The application root must be `passenger/` adjacent to `current/` for this code. The selected Passenger interpreter must be the Smart Living virtualenv interpreter. Test:

```bash
"$VENV_BIN/python" "$PASSENGER_ROOT/passenger_wsgi.py"
```

A successful import returns without a traceback. This is not an HTTP or database workflow test.

Keep panel-generated Passenger directives unless support requires a manual configuration. If using manual Apache configuration, the three core directives are:

```apache
PassengerAppRoot "/home/CPANEL_USER/apps/smartliving/passenger"
PassengerBaseURI "/"
PassengerPython "/ACTUAL/SMARTLIVING/VIRTUALENV/bin/python"
```

These are templates, not literal paths. Back up `$DOC_ROOT/.htaccess` before editing; preserve other necessary host directives. Never copy SEAS/WordPress `.htaccess`. If WordPress rules reappear, correct the document root/tool configuration before continuing.

## 8. Validate code and apply migrations

For an existing database, complete step 14's backups and a maintenance window before migrations. A fresh empty database has no business data to back up yet.

```bash
cd "$RELEASE_ROOT"
"$VENV_BIN/python" manage.py check
"$VENV_BIN/python" manage.py makemigrations --check --dry-run
"$VENV_BIN/python" manage.py check --deploy
"$VENV_BIN/python" manage.py migrate --plan
```

Expect no normal system-check errors and no migration drift. Run `production_check --settings=config.production`. Production enables one-hour HSTS. W005/W021 are deliberately acknowledged because unreviewed child hosts and browser preload are not enabled; other deployment warnings fail the application preflight.

If TLS terminates at a reverse proxy, support must confirm that it strips client-supplied X-Forwarded-Proto and sets its own value. Only then set `DJANGO_TRUST_X_FORWARDED_PROTO=True`; the production profile reads this opt-in. Resolve redirect loops before launch.

Then:

```bash
"$VENV_BIN/python" manage.py migrate --noinput
"$VENV_BIN/python" manage.py showmigrations --plan
"$VENV_BIN/python" manage.py migrate --check
```

Do not generate new migration files on production. Fix migration drift in development and deploy the reviewed migration files.

## 9. Choose the initial data path

Choose **A or B**; do not blindly combine a fixture import with a seed import.

### A. Fresh production database

```bash
"$VENV_BIN/python" manage.py createsuperuser
"$VENV_BIN/python" manage.py seed_smartliving_categories
"$VENV_BIN/python" manage.py seed_sales_roles
```

Optional supplied manufacturer catalogue, after reviewing content/media rights and business suitability:

```bash
"$VENV_BIN/python" manage.py seed_manufacturer_catalogue --expected-count 500 --dry-run
"$VENV_BIN/python" manage.py seed_manufacturer_catalogue --expected-count 500 --publish
```

Without `--publish`, newly imported products are drafts. Reruns preserve existing products, staff edits and publication decisions; `--publish` does not publish existing drafts. Keep `manifest.json` and its complete `assets/` together. The importer validates checksums and runs offline. See [bundle instructions](../catalogue_seed/manufacturers/README.md).

### B. Transfer the approved existing local data

Use only for a **new empty production business database** after migrations and before creating production users/settings. Do not load a full fixture over live enquiries. Freeze edits during the export and media copy. Exports contain personal data and password hashes; transfer privately, restrict access and remove temporary copies when verified.

In local Windows PowerShell, with the intended source database configured in local `.env`:

```powershell
Set-Location D:\ProjectPy\smartliving
New-Item -ItemType Directory -Force var | Out-Null
.\.venv\Scripts\python.exe manage.py shell -c "from django.db import connection; from apps.catalogue.models import Product; print(connection.vendor, 'products:', Product.objects.count())"
.\.venv\Scripts\python.exe manage.py dumpdata --natural-foreign --natural-primary --exclude contenttypes --exclude auth.permission --exclude sessions --exclude admin.logentry --exclude catalogue.productsearchtoken --output var/production-transfer.json
```

This exports the configured source, whether MySQL or SQLite. Do not change local database credentials to production to generate this export. Review which users, leads, CMS and business data should go live. Do not use `scripts/setup_local_mysql.py` on the server: it is a local provisioning tool with different defaults.

Upload the fixture to `$APP_ROOT/backups/production-transfer.json` privately, then on the server:

```bash
"$VENV_BIN/python" manage.py loaddata "$APP_ROOT/backups/production-transfer.json"
"$VENV_BIN/python" manage.py seed_sales_roles
"$VENV_BIN/python" manage.py changepassword APPROVED_ADMIN_USERNAME
```

Compare counts of products, images, enquiries, proposals, users and site settings against the source. Confirm image paths actually resolve after step 10. If import fails, stop and diagnose against this empty target; never repeatedly overwrite an active business database. A MySQL-to-MySQL native export/import is another option when source/target versions and schemas match, but use a separate fresh database and verify the restore before traffic.

For both paths:

```bash
"$VENV_BIN/python" manage.py rebuild_product_search
```

## 10. Transfer media and expose public assets

Fixture exports do not contain image/document bytes. For path B, securely copy the contents of local `D:\ProjectPy\smartliving\media\` into `$SHARED_ROOT/media/`, preserving relative directories and filenames. Avoid `media/media/`. For path A's catalogue import, the importer copies bundled assets into configured media storage.

Collect static and create public links once:

```bash
"$VENV_BIN/python" manage.py collectstatic --noinput
ln -s "$SHARED_ROOT/staticfiles" "$DOC_ROOT/static"
ln -s "$SHARED_ROOT/media" "$DOC_ROOT/media"
```

If links already exist, inspect them instead of recreating them. If the host forbids public symlinks, ask support for web-server aliases mapping `/static/` and `/media/` to these exact shared directories. A one-time copy of media is not sufficient for subsequent uploads. `MEDIA_ROOT`/`STATIC_ROOT` environment variables are not supported by the current settings; directory links or a reviewed settings change are needed.

The host must serve these directories before routing other requests to Passenger, disable directory listings and script execution under `/media/`, and set appropriate content types. Keep `shared/var/private_imports` private; never link it to the public root. Product PDFs/images are public content: do not upload confidential customer material there.

Test `/static/admin/css/base.css` and an actual product media URL over HTTPS. Both must return the file, not a Django 404 or application HTML. With `DEBUG=False`, Django does not serve uploaded media through its development URL helper. `collectstatic` never copies uploaded product media.

## 11. Configure business identity, content and staff

In `/admin/`:

1. Open **Site settings** and edit the existing record (or create the initial one). Confirm business name, public URL, email, phone, address, hours, WhatsApp digits including country code, logo/favicon, colours and SEO. Avoid duplicate site-settings rows; the app reads the first.
   Contact values supplied on 15 October 2026: **Phone** `+918668329719`,
   **WhatsApp number** `918668329719` (digits only), **Email** `ssepadrauna@gmail.com`.
   Enable **Show WhatsApp**. These values are saved in the local MySQL database;
   when updating an existing production database, edit its existing Site settings row
   in Admin rather than replacing its database with the local copy. Verify product-page
   and footer WhatsApp links, the enquiry-page contact actions, and the tel/mailto links.
2. Review CMS pages/sections, navigation, category and brand content. Replace demo/legal/contact text with approved facts.
3. Confirm product descriptions, model/region compatibility, publication flags, documents, prices/quote wording, availability and media permission. Imported internal `SL-...` SKUs are not manufacturer model numbers or a stock guarantee.
4. Create individual approved staff accounts with strong passwords, mark them staff and assign **Sales viewer** or **Sales operator**. Reserve superuser access for owners/admins.
5. Survey viewing additionally needs `leads.view_consultation`; editing needs `leads.change_consultation` and `leads.view_enquiry`. The role seed does not grant survey permissions. Grant them explicitly to approved staff.
6. Business data imports/exports also have custom permissions; grant only to authorized staff after testing their access.

Enquiries are stored for staff follow-up. Marking a quotation sent records manual delivery; it does not email it. Automatic email/WhatsApp, payments and accounting integration are not implemented. SEAS SMTP environment variables alone do not enable those features here.

## 12. Start/restart and verify the live site

Run:

```bash
"$VENV_BIN/python" manage.py check
"$VENV_BIN/python" "$PASSENGER_ROOT/passenger_wsgi.py"
mkdir -p "$PASSENGER_ROOT/tmp"
touch "$PASSENGER_ROOT/tmp/restart.txt"
```

Use the panel's **Restart** action if required by the host, especially after environment changes. Verify response and redirect behavior:

```bash
curl -I http://smartliving.seas-india.com/
curl -I https://smartliving.seas-india.com/
curl -I https://smartliving.seas-india.com/static/admin/css/base.css
```

HTTP should redirect to HTTPS; HTTPS should finish with a successful response and no redirect loop. Follow redirects with `curl -IL --max-redirs 5` if needed. This project has no dedicated `/health/live/` endpoint; do not copy the Munshiiji health check.

Perform these in desktop and mobile/private browser sessions:

- Home, navigation, footer, categories, brands, pagination, filters and product detail render correctly.
- Search suggestions (two or more characters) and full search find an existing model; product images/documents load.
- Add/remove quote-list items and submit a test quote request with consent; confirm it appears in `/workspace/enquiries/`.
- Submit product and contact enquiries and confirm stored details.
- Submit a future site-survey time in IST; authorized staff can manage it, unauthorized staff cannot.
- Sign in to Admin; CSS/JS load; upload one approved test image and confirm it displays after a restart.
- Exercise quotation draft, edit, mark sent and print/save PDF with test data; check viewer/operator permissions using separate accounts. Do not send a test quotation to a customer.
- Verify WhatsApp/contact destinations, privacy/terms, `/robots.txt`, `/sitemap.xml`, canonical URLs and a nonexistent-page 404.
- Check `/.env`, `/manage.py`, `/db.sqlite3`, `/var/private_imports/` and known backup/fixture paths disclose no contents (403/404 expected).
- Confirm HTTPS cookies have Secure flags and error pages do not expose tracebacks.

Record release/version, operator, time, check outputs and smoke-test result privately. A successful package install, import test or panel toast does not prove these workflows work.

## 13. Troubleshooting

| Symptom | Check and action |
|---|---|
| Passenger 500/503 | Run startup-file import with the selected virtualenv. Check module paths, package installation, environment and panel Passenger log. |
| `DisallowedHost` / 400 | Exact hostname in `DJANGO_ALLOWED_HOSTS`; remove schemes/paths there. Restart after changes. |
| CSRF 403 | Use exact HTTPS origin in `DJANGO_CSRF_TRUSTED_ORIGINS`; check HTTPS detection and browser cookies. Do not disable CSRF. |
| Redirect loop | Verify trusted proxy HTTPS scheme handling; do not blindly trust incoming forwarded headers. |
| MySQL access denied / unknown database | Full cPanel-prefixed names, database-scoped privileges, password, host/port and effective panel-variable overrides. |
| Missing tables / unexpected empty catalogue | Verify effective DB engine, intended DB and migrations; a missing engine variable can select SQLite. |
| Static or image 404 | Public mapping, symlinks, traversal permissions, actual files, collectstatic; verify media copied separately. |
| Upload/import permission error | Writable shared media and private imports, disk/inode quota, account ownership. Never use 777. |
| Search empty after import | Run `rebuild_product_search`; confirm products are active/published. |
| Survey access denied | Staff flag plus consultation/view enquiry permissions; sales seed alone is insufficient. |
| WordPress page appears | Subdomain document root or inherited rewrite configuration is wrong; correct only Smart Living's mapping. |

Diagnostics:

```bash
cd "$RELEASE_ROOT"
"$VENV_BIN/python" manage.py check
"$VENV_BIN/python" manage.py migrate --check
"$VENV_BIN/python" "$PASSENGER_ROOT/passenger_wsgi.py"
tail -n 100 "$APP_ROOT/logs/passenger.log"
```

The log path must match the host's configured Passenger log. Also inspect **cPanel → Metrics → Errors**, the application panel and support-provided Apache logs. Current Django settings do not define a file logger; do not assume `django.log` exists. Redact secrets and customer data before sharing tracebacks; never publish `diffsettings`, `.env` or full connection settings.

## 14. Backups, monitoring and scheduled maintenance

Before every update/import and at least daily once accepting enquiries:

1. Back up the MySQL database using cPanel Backup or phpMyAdmin Export (SQL format with structure and data). Record the exact database and timestamp. Keep passwords out of command arguments/history.
2. Back up media and configuration privately. In the initialized server session:

```bash
export BACKUP_TAG="$(date +%Y%m%d-%H%M%S)"
mkdir -p "$APP_ROOT/backups/$BACKUP_TAG"
tar -czf "$APP_ROOT/backups/$BACKUP_TAG/media.tar.gz" -C "$SHARED_ROOT" media
cp "$RELEASE_ROOT/.env" "$APP_ROOT/backups/$BACKUP_TAG/production.env"
cp "$PASSENGER_ROOT/passenger_wsgi.py" "$APP_ROOT/backups/$BACKUP_TAG/passenger_wsgi.py"
"$VENV_BIN/python" -m pip freeze > "$APP_ROOT/backups/$BACKUP_TAG/requirements.txt"
```

3. Keep the matching source release/migrations and document-root config backup. Store an encrypted off-host copy, restrict backup access and define retention based on lead volume and recovery requirements (for example daily backups plus weekly copies). Monitor backup failures and available space.
4. Before launch and periodically, restore SQL + matching media + code into a separate private test database/app. Confirm counts, login, sample images, enquiries and quotations. A backup file's existence is not proof it can restore.
5. Set an external HTTPS uptime check for `/` and monitor TLS expiry, 5xx logs, failed form submissions, storage/inodes and database limits. Current settings have no configured error-email/monitoring backend; choose and verify one or review logs operationally.
6. Add a daily **cPanel → Cron Jobs** command for expired sessions, replacing both paths with actual absolute paths:

```text
/ACTUAL/SMARTLIVING/VIRTUALENV/bin/python /home/CPANEL_USER/apps/smartliving/current/manage.py clearsessions
```

Do not paste `$VENV_BIN` into cron: interactive shell variables are absent there. There are no required SEAS lead-sync jobs or automatic catalogue scraper jobs for this application. Rebuild search after bulk updates, raw fixtures or external imports; normal product/brand saves update it automatically.

## 15. Subsequent production updates

1. Test the proposed release in development/staging, including migrations and affected workflows. Preserve a source release identifier and dependency versions.
2. Take step 14's verified database/media/config backups. Record the old source and package versions.
3. Announce a maintenance window and pause writes. Use a host maintenance page/access restriction if replacing files in `current/`; prevent customers using a partially uploaded release.
4. Upload the reviewed source/migrations to `current/` without overwriting `.env` or the `media`, `staticfiles`, `var` links. For managed release directories, retain equivalent links and test before activation; do not mix layouts mid-update.
5. Activate the actual Smart Living virtualenv and initialize step 2's variables.
6. Run the commands below one at a time. Stop on the first failure:

```bash
cd "$RELEASE_ROOT"
"$VENV_BIN/python" -m pip install -r requirements-production.txt
"$VENV_BIN/python" -m pip check
"$VENV_BIN/python" manage.py check
"$VENV_BIN/python" manage.py makemigrations --check --dry-run
"$VENV_BIN/python" manage.py check --deploy
"$VENV_BIN/python" manage.py migrate --plan
"$VENV_BIN/python" manage.py migrate --noinput
"$VENV_BIN/python" manage.py seed_sales_roles
"$VENV_BIN/python" manage.py rebuild_product_search
"$VENV_BIN/python" manage.py collectstatic --noinput
"$VENV_BIN/python" manage.py migrate --check
"$VENV_BIN/python" "$PASSENGER_ROOT/passenger_wsgi.py"
mkdir -p "$PASSENGER_ROOT/tmp"
touch "$PASSENGER_ROOT/tmp/restart.txt"
```

7. Repeat affected step 12 checks, reopen writes, watch logs and verify an actual enquiry. Keep backups until the new version is accepted.

Do not run `createsuperuser`, full fixture imports or publish catalogue seeds on every update. Do not run large synthetic benchmarks on the production business database. Shared static files are updated in place here, so the maintenance window also covers static collection.

## 16. Rollback and recovery

1. Put Smart Living into maintenance mode and pause writes. Record the failure and last known good release; preserve logs privately.
2. If no migrations/data changes occurred and old code remains compatible, restore the previous reviewed source and dependency versions. Preserve production `.env` and shared media/private directories, recollect old static, test the WSGI import and restart Passenger.
3. If schema/data changed incompatibly, do not simply deploy old code or run guessed reverse migrations. Restore the matching pre-update SQL backup into a separate recovery database first, paired with its code and media snapshot. Verify there before a controlled database/config switch.
4. A database restore can discard enquiries received since the backup. Preserve/reconcile those records with the owner before restoring over an active database. Keep a copy of the failed current database and media.
5. Re-run search rebuild, Django checks and browser smoke tests against the recovered database; restart and reopen traffic only when verified. Record actual recovery time and data-loss interval.

## 17. Launch acceptance record

Do not mark production ready until all are recorded:

- [ ] Actual account, DNS address, document root, Passenger path and virtualenv confirmed.
- [ ] Unique secrets, `DEBUG=False`, explicit MySQL engine and production connection verified.
- [ ] Valid HTTPS, correct redirects/scheme detection, secure cookies and reviewed deployment warnings.
- [ ] Migrations applied; intended data counts, search and persistent media verified.
- [ ] Business/legal/content/media rights reviewed; individual staff permissions tested.
- [ ] All enquiry, survey, quote-list and quotation smoke tests passed over the real hostname.
- [ ] Private files inaccessible; public upload execution disabled; logs accessible privately.
- [ ] Database/media/config backup, off-host copy, restore test and monitoring in place.
- [ ] Source/package version and rollback procedure recorded.

## References and validation limits

Repository references: `config/settings.py`, `config/wsgi.py`, `config/urls.py`, `.env.example`, `requirements-production.txt`, sales role and catalogue management commands, and the SEAS production command guide. This document adapts that guide; SEAS-specific release paths, image compression scripts, SMTP and deployment scripts are not Smart Living commands.

Official references checked while preparing this guide:

- [Django 5.2 deployment checklist](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/): production settings, backups, static/media and WSGI deployment.
- [Django proxy HTTPS setting](https://docs.djangoproject.com/en/5.2/ref/settings/#secure-proxy-ssl-header): trust conditions for forwarded HTTPS headers.
- [cPanel Python WSGI deployment](https://docs.cpanel.net/knowledge-base/web-services/how-to-install-a-python-wsgi-application/) and [Application Manager](https://docs.cpanel.net/cpanel/software/application-manager/): host-supported Passenger registration. CloudLinux panel labels and interpreter paths depend on the provider.

Back up private documents as well as media and database; use the current `backup_site` command and restore procedure in PRODUCTION_LAUNCH.md. Product documents are now private on disk and downloaded through permission-checked /documents/ routes. Run secure_product_documents for files from older releases.

This is an operator guide, not evidence of a live deployment. Server paths, DNS, TLS/proxy configuration, database restore and production browser acceptance require execution and verification on the actual hosting account.
