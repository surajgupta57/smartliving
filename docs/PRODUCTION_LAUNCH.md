# Smart Living: cPanel production launch

> **Current hosting instructions (16 October 2026):** follow [the working cPanel configuration](CPANEL_WORKING_CONFIGURATION.md). The owner reported the site working after replacing the recursive Passenger loader and using real public static/media directories. The older symlink layout below is not the layout to reapply on this account. The updated deployer supports these public roots; follow [the automation setup](DEPLOYMENT_AUTOMATION.md) before its first run.

Target: **https://smartliving.seas-india.com**. This procedure uses a separate Python App / Passenger registration, MySQL database, source directory and public document root for Smart Living.

The application has been prepared locally. These instructions do not mean DNS, the hosting environment or production traffic has been verified.

## 1. Prepare the hosting account

Confirm Python 3.12 (preferred), or a patched Python 3.11 version at least 3.11.5, MySQL 8, mysqlclient build support, HTTPS, SSH/Terminal, cron, adequate disk/inodes, error logs, ModSecurity/WAF and a restorable off-host backup facility. Ask the host to apply request-size limits and abuse/rate controls to `/admin/login/` and the public enquiry POST endpoints. The application does not claim to provide a distributed WAF or MFA.

Use only the Smart Living subdomain and app. Preserve SEAS configuration and data.

Suggested paths (use your actual account home):

```bash
export APP_ROOT="$HOME/apps/smartliving"
export RELEASE_ROOT="$APP_ROOT/current"
export SHARED_ROOT="$APP_ROOT/shared"
export PASSENGER_ROOT="$APP_ROOT/passenger"
export DOC_ROOT="$HOME/public_html/smartliving"
umask 077
mkdir -p "$RELEASE_ROOT" "$PASSENGER_ROOT" "$SHARED_ROOT/media" "$SHARED_ROOT/staticfiles" "$SHARED_ROOT/var/private_imports" "$SHARED_ROOT/var/private_documents" "$APP_ROOT/backups" "$APP_ROOT/logs" "$DOC_ROOT"
```

Source, credentials, backups, imports and private documents must remain outside the public document root. Only static assets and ordinary media get public aliases. Public media must not execute scripts. Do not use permissions 777.

## 2. Upload the clean release

Use `deploy/releases/smartliving-production.zip` and verify its adjacent SHA256 file. Extract the source into `$RELEASE_ROOT` with `manage.py` directly inside that directory. Do not extract it under public_html. The ZIP deliberately excludes `.env`, local databases, media, private files, backups, generated static, local virtualenvs and demo/QA artifacts.

For a new deployment only, link persistence before generating files:

```bash
ln -s "$SHARED_ROOT/media" "$RELEASE_ROOT/media"
ln -s "$SHARED_ROOT/staticfiles" "$RELEASE_ROOT/staticfiles"
ln -s "$SHARED_ROOT/var" "$RELEASE_ROOT/var"
```

If a destination already exists, inspect and back up its contents before replacing it. Never remove uploaded data just to make a symlink command succeed. Keep persistence across releases.

The optional manufacturer seed is not included in the default source ZIP. Use `scripts/build_release.py --include-catalogue` if a clean first install needs that offline seed. Transfer existing business data, public media and private documents separately through private storage. Changing the database engine does not transfer data.

## 3. Register Passenger and install the tested packages

In cPanel **Setup Python App**, register:

- Application root: `apps/smartliving/passenger`.
- URL: `smartliving.seas-india.com`, path `/`.
- Startup file: `passenger_wsgi.py`; entry point: `application`.
- Interpreter: the separate Smart Living virtualenv, Python 3.12 preferred (or patched 3.11, minimum 3.11.5).

Activate the environment using the exact command supplied by cPanel:

```bash
export VENV_BIN="${VIRTUAL_ENV:?Activate the Smart Living environment}/bin"
cd "$RELEASE_ROOT"
"$VENV_BIN/python" -m pip install -r requirements-production.txt
"$VENV_BIN/python" -m pip check
cp deploy/cpanel/passenger_wsgi.py "$PASSENGER_ROOT/passenger_wsgi.py"
```

The shipped startup defaults to the layout above. For a different layout, set `SMARTLIVING_PROJECT_ROOT` in cPanel to the absolute source root. It always selects `config.production`, rather than inheriting development settings.

## 4. Create private production settings

Create a new database and database-scoped user in cPanel. Set real full prefixed names and a strong generated password. Do not reuse the SEAS database, users or environment file.

Generate a private file on the server:

```bash
cd "$RELEASE_ROOT"
"$VENV_BIN/python" scripts/init_production_env.py --output "$RELEASE_ROOT/.env"
chmod 600 "$RELEASE_ROOT/.env"
```

The command generates a secret without printing it and refuses to overwrite an existing file. Alternatively upload the locally generated `.env.production` privately and rename it `.env`. Fill its database placeholders privately using cPanel File Manager. Do not paste secrets into chat, screenshots or source control.

Use MySQL host/port supplied by the host; port 3307 belongs to local development, not the hosting default. `DJANGO_ENV=production`, exact allowed hosts, exact HTTPS CSRF origins and `DJANGO_DB_ENGINE=mysql` are mandatory. Debug is forced off. Missing/placeholder secrets and database values, wildcard hosts, disabled HTTPS and overlapping public/private roots fail startup.

By default `.env` is read from the source root. To keep it elsewhere, set `DJANGO_ENV_FILE` to its absolute private path in cPanel. Environment variables already set in cPanel take precedence over the file; remove stale duplicated settings. Do not `source .env` in Bash.

The production profile enables secure, host-only Smart Living session/CSRF cookies, HTTPS redirects and one-hour HSTS. HSTS does not include child subdomains and is not submitted for browser preload; Django W005/W021 are intentionally acknowledged by `production_check`. Other deployment warnings fail that preflight. Increase HSTS duration only after verifying the actual host's HTTPS behavior.

If the host terminates TLS at a proxy, ask support whether it **strips client X-Forwarded-Proto and sets its own trusted value**. Only after confirmation set `DJANGO_TRUST_X_FORWARDED_PROTO=True`. It defaults to False. Do not solve a redirect loop by disabling secure cookies or trusting arbitrary forwarded headers.

## 5. Back up, migrate, and secure documents

Before updating an existing installation, take a verified database/media/private-document/config backup and use a maintenance window. On a new empty database, run:

```bash
"$VENV_BIN/python" manage.py production_check --configuration-only --settings=config.production
"$VENV_BIN/python" manage.py migrate --plan --settings=config.production
"$VENV_BIN/python" manage.py migrate --noinput --settings=config.production
```

Restore or import approved catalogue/business data into the separate target database when applicable. Transfer existing media privately to shared media and private documents to shared var/private_documents.

For older releases with documents under public media:

```bash
"$VENV_BIN/python" manage.py secure_product_documents --dry-run --settings=config.production
"$VENV_BIN/python" manage.py secure_product_documents --remove-public-copies --settings=config.production
```

This command checks all paths/conflicts, copies into private storage, verifies SHA256 before removing public copies, and preserves database filenames. It refuses missing files or conflicting content. On a fresh database with no documents it is a no-op. On current releases new product files are private automatically.

All product document links now use `/documents/...` permission-checked attachments. Published public datasheets remain downloadable. Hidden/unpublished or staff-only documents return 404 unless the reader is active authorised staff with `catalogue.view_productdocument`. Do not alias private documents into Apache.

```bash
"$VENV_BIN/python" manage.py rebuild_product_search --settings=config.production
"$VENV_BIN/python" manage.py seed_sales_roles --settings=config.production
"$VENV_BIN/python" manage.py createsuperuser --settings=config.production
"$VENV_BIN/python" manage.py collectstatic --noinput --settings=config.production
```

Create a superuser only if needed; do not create shared staff logins. Mark approved users as staff and assign Sales viewer/operator groups. These groups do not create or assign accounts automatically. Complete real business name, email, phone, address, public URL and approved published catalogue content in Admin.

## 6. Serve public files and restart

Create host-approved aliases or symlinks for `/static/` -> shared/staticfiles and `/media/` -> shared/media. Static/media directories need host-appropriate public read/traversal permission; private var and secrets stay restricted.

Use `deploy/cpanel/public.htaccess.example` as an additional protection example in the Smart Living public document root, preserving generated Passenger directives. Copy `deploy/cpanel/media.htaccess` to shared/media/.htaccess. Confirm the host permits these directives and that script requests are denied. If .htaccess causes HTTP 500, ask support for equivalent supported protection rather than exposing scripts.

Import-test the startup file with the actual virtualenv, then use cPanel **Restart**. Do not use runserver for public traffic.

```bash
"$VENV_BIN/python" "$PASSENGER_ROOT/passenger_wsgi.py"
"$VENV_BIN/python" manage.py production_check --settings=config.production
"$VENV_BIN/python" scripts/smoke_production.py --url https://smartliving.seas-india.com
```

The full preflight checks database access, migrations, required manifest assets, writable storage, relocated files, business identity and an active operator. It does not create business data or grant access.

## 7. Required host acceptance

- DNS and valid TLS serve only the intended hostname, with no redirect loop.
- `/health/live/` returns 200 without querying the database. `/health/ready/` returns 200 with the database available, otherwise a generic 503. Both are uncached and reveal no configuration.
- A collected stylesheet/script and a product image return 200. Admin and workspace styles render correctly with DEBUG off.
- `/.env`, `/manage.py`, `/db.sqlite3`, `/var/private_imports/`, private documents and backup paths reveal no contents.
- A public product datasheet downloads, and a staff-only document fails for an anonymous browser even when its URL is known. Old `/media/products/documents/...` URLs are gone.
- Create an enquiry with customer consent, sign in as approved staff, record a call, set a follow-up, verify Notifications, schedule a survey and complete a quotation including PDF export. Verify a viewer cannot change records. Use an explicitly labelled launch-test enquiry and manage it through the normal record-retention process.
- Verify on real phone/tablet devices. Viewport tests do not test physical keyboards, mobile browser versions or network conditions.
- Verify private logs are captured and monitored; database/backup failures are actionable.
- Configure host/WAF login and public-form abuse controls, and verify trusted client-IP handling with support. Do not trust arbitrary client-forwarded addresses.

## 8. Backups, cron and a restore rehearsal

The new backup command uses a private temporary MySQL option file; passwords are not placed in process arguments. It creates database.sql.gz, media.tar.gz, private_documents.tar.gz and a SHA256 manifest in a timestamped private directory. Failures retain an INCOMPLETE marker. It never archives environment secrets; keep the matching source release and private configuration separately in encrypted storage.

```bash
"$VENV_BIN/python" manage.py backup_site --output-dir "$APP_ROOT/backups" --settings=config.production
```

If mysqldump is not on PATH, use `--mysqldump /HOST/SUPPLIED/PATH/mysqldump`. Do not run schema migrations during a dump; pause uploads during a coordinated database/file snapshot when consistency requires it. Monitor exit status and disk space. Encrypt and copy backups off-host; define retention for business needs. Do not automatically purge the only recoverable copy.

Set cPanel cron using absolute interpreter and source paths, e.g. daily backup and daily `manage.py clearsessions --settings=config.production`, with output to private logs. Cron is not required for in-portal follow-up notifications.

Before launch, restore the SQL into a **different private test database**, paired with matching media/private documents and code. The SQL dump deliberately omits CREATE DATABASE / USE directives. With a private restore client option file and a deliberately selected restore database, import the decompressed SQL; never target the active database. Verify table counts, login, public/staff document permissions, images, enquiry history and quotation totals. Verify archive hashes before extraction and reject unsafe/symlink archive members. A completed backup command is not proof that a restore works.

## 9. Updates and rollback

Keep the previous code archive, pinned package set, database, media/private-document snapshot and private environment backup. Rehearse updates separately, then back up and run configuration checks, migration plan, migrations, document relocation if needed, search rebuild and collectstatic. Restart Passenger, run full preflight/HTTPS probes and repeat affected browser workflows.

For a code-only compatible rollback, restore the previous source and tested dependencies while preserving shared storage. If schema/data changed incompatibly, first restore matching code/database/files into a separate recovery app. Do not run guessed reverse migrations or overwrite live data. Reconcile enquiries received since a backup before any database switch.

## Local evidence

See the generated production-readiness report for actual completed checks. Server credentials, DNS, TLS/proxy policy, Apache directives, host filesystem permissions, cron/off-host backups, restore rehearsal and production browser acceptance require execution on the cPanel account.

Sources: [Django deployment checklist](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/), [trusted proxy HTTPS setting](https://docs.djangoproject.com/en/5.2/ref/settings/#secure-proxy-ssl-header), [supported Django releases](https://www.djangoproject.com/download/).
