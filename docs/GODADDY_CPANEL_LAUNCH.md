# Smart Living on GoDaddy Economy cPanel: first launch and operations

> **Current hosting instructions (16 October 2026):** follow [the working cPanel configuration](CPANEL_WORKING_CONFIGURATION.md). The owner reported the site working after replacing the recursive Passenger loader and using real public static/media directories. The older symlink layout below is not the layout to reapply on this account. The updated deployer supports these public roots; follow [the automation setup](DEPLOYMENT_AUTOMATION.md) before its first run.

Prepared 16 October 2026. Target: **https://smartliving.seas-india.com**.
You confirmed that **Setup Python App** is available. The actual Python version,
database version, resource limits and hosting filesystem rules still need checking.
These instructions prepare a separate Smart Living application; they do not mean
that deployment or live acceptance has already succeeded.

For one-command GitHub updates after the initial setup, follow
[deploy/README.md](../deploy/README.md). It includes the one-time transition from
this manual current/ directory to managed releases, maintenance handling and
release-specific static files. Do not mix its static layout with step 13 below
without completing that transition.

**Follow the numbered steps in order. Run server commands one at a time and stop
if any command fails.** Windows commands are marked PowerShell; hosting commands
are Bash. Do not paste Bash into Windows PowerShell. Do not use Django runserver,
nohup or a background development server to serve the public site.

## 1. Check the account before uploading

GoDaddy > My Products > Web Hosting > the account hosting seas-india.com > Manage
> cPanel Admin. Record the cPanel username, account home and server IPv4 address.
Do not assume the server IP is the address of the current SEAS DNS record if a
proxy or CDN is in use.

Check these items in cPanel or with GoDaddy support:

| Item | Required result |
|---|---|
| Python App | A new application can be created for the subdomain without changing SEAS |
| Python | Prefer a current patched 3.12; patched 3.11 is an alternative subject to the pinned package installation check |
| Database | MySQL 8.0.11+ or MariaDB 10.5+ compatible with Django 5.2; use a maintained server release |
| Driver | The pinned mysqlclient package can install and import in this Python environment |
| SSH / Terminal | You can activate the app environment and run management commands |
| Domains / databases | This account permits the new subdomain/app and a separate database/user |
| Public files | Apache can serve the app's static/media directories using approved symlinks or aliases |
| Storage / limits | Disk, inode, CPU, memory, process and database limits leave room for both applications, imports and backups |
| HTTPS | A certificate can cover smartliving.seas-india.com |
| Backups | Private dumps, file backups, off-host copies and a restore test are available |

Python language support by itself does not establish Django/Passenger support.
The Economy name also does not establish this account's entitlements. You have
confirmed the Python App feature, but its versions and database support are the
remaining gates. If only an old database or interpreter is available, ask support
for a compatible environment before proceeding; do not downgrade application
security to fit an unsupported server.

GoDaddy documents [supported components and tier differences](https://www.godaddy.com/en-uk/help/article/which-components-does-my-hosting-support-5614?locale=en).
The database requirements above come from [Django 5.2](https://docs.djangoproject.com/en/5.2/ref/databases/).

If Terminal is missing, enable SSH in GoDaddy Hosting Dashboard > Settings >
SSH access > Manage, then connect using the host and port GoDaddy displays.
Use [GoDaddy's SSH instructions](https://www.godaddy.com/en-ca/help/enable-ssh-for-my-web-hosting-cpanel-account-16102).

## 2. Record and protect the existing SEAS setup

Before account changes, use the hosting backup facility to retain a recoverable
copy of the SEAS files, database and configuration. Record its current document
root, Python App registration if any, and DNS records. Keep those records private.

Smart Living needs its own database, virtualenv, app root, document root and
secret. Do not replace the SEAS root .htaccess, change the main domain's DNS,
alter mail records, reuse the SEAS database or register Smart Living over its app.
Separate applications in one cPanel account still share account resources and
the hosting account's operating-system access; they are not a VPS security boundary.

## 3. Create the subdomain and DNS record

In cPanel > Domains > Create A New Domain:

| Field | Value |
|---|---|
| Domain | smartliving.seas-india.com |
| Share document root | Unchecked |
| Document root | public_html/smartliving |

Record the resulting absolute document root. If this path already contains files,
stop and identify the application they belong to before changing anything.
Older panels may offer a Subdomains screen instead. The important result is a
separate document root. See [cPanel's subdomain instructions](https://support.cpanel.net/hc/en-us/articles/360052780313-How-to-create-a-subdomain).

In the **authoritative DNS provider** for seas-india.com, check whether a record
for smartliving was already created. If not, add:

| Type | Name | Value | TTL |
|---|---|---|---|
| A | smartliving | Actual GoDaddy hosting IPv4 | Provider default |

Do not create duplicate/conflicting A/CNAME records for the same name. Change
only this subdomain's existing record if it points somewhere else and you intend
to move it. Add AAAA only when support confirms working IPv6 for this application.
Do not change nameservers or the root domain just to add this app. If DNS is
managed outside GoDaddy, make the record there rather than in an unused zone.

From Windows PowerShell:

```powershell
Resolve-DnsName smartliving.seas-india.com
```

Expected: the intended hosting address, or the intended proxy path if using a
deliberately configured CDN. Allow for the existing record's TTL; do not assume
an exact propagation time.

## 4. Obtain HTTPS for the exact subdomain

In GoDaddy's hosting Dashboard > Security and cPanel > SSL/TLS Status, inspect
the certificate for smartliving.seas-india.com. GoDaddy currently describes
integrated DV SSL for primary domains and subdomains, but confirm the entitlement,
issuance and installation on this account. A certificate only for seas-india.com
does not automatically prove coverage for this hostname.

See [GoDaddy integrated SSL](https://www.godaddy.com/help/activate-an-integrated-ssl-32040).
If automatic issuance is not available, use the host-supported certificate
installation process. Verify the browser certificate has the intended hostname
and no certificate warning before final app testing.

The app enforces HTTPS. If TLS is terminated by a proxy, ask support whether it
strips incoming X-Forwarded-Proto and sets its own trusted value. Only after that
confirmation enable DJANGO_TRUST_X_FORWARDED_PROTO in step 10. An HTTPS redirect
loop must be resolved before launch.

## 5. Build the source release on the local computer

In Windows PowerShell:

```powershell
Set-Location D:\ProjectPy\smartliving
.\.venv\Scripts\python.exe scripts/build_release.py
Get-FileHash deploy/releases/smartliving-production.zip -Algorithm SHA256
```

Files produced:

- deploy/releases/smartliving-production.zip
- deploy/releases/smartliving-production.sha256

The builder includes current code, templates, migrations, CMS content command,
production helpers and deployment documentation. It excludes credentials, local
databases, virtualenvs, live media and generated static files. The normal source
release intentionally does not include the manufacturer seed asset bundle.

Build again after later local code edits. Do not upload an old ZIP from an earlier
session and assume it contains the latest CMS/security work.

## 6. Export the catalogue and CMS locally

This section is for a **new, empty production catalogue/CMS**. It transfers local
IDs and is not a merge procedure for an already populated live catalogue.
Pause local content edits/uploads until the JSON and file copies are complete.

In Windows PowerShell:

```powershell
New-Item -ItemType Directory -Force tmp/production-transfer | Out-Null
.\.venv\Scripts\python.exe -X utf8 manage.py dumpdata catalogue cms core.SiteSettings --exclude catalogue.ProductSearchToken --indent 2 --output tmp/production-transfer/catalogue-and-content.json
```

This includes brands, categories, products, galleries, features, specifications,
document records, compatibility links, planning profiles, CMS pages, homepage
sections, FAQs and Site settings. It excludes users/passwords, enquiries,
quotations, sessions and abuse counters. Search tokens are rebuilt on the server.
JSON contains file paths; it does not contain the image/PDF file bytes.
Keep the -X utf8 option on Windows: product specifications contain Unicode symbols
that can fail to export with the system's legacy text encoding. A failed or
partially written export must not be uploaded as the final fixture.

Copy the contents of both local storage directories separately:

| Source on Windows | Destination on host |
|---|---|
| media/ contents | shared/media/ |
| var/private_documents/ contents | shared/var/private_documents/ |

Preserve paths. For example media/products/gallery/example.jpg must become
shared/media/products/gallery/example.jpg, not shared/media/media/products/...
Documents remain under private storage, never under the public document root.
If your local storage paths have been customised, use their actual configured
locations instead of these defaults.

Use SFTP or cPanel upload over HTTPS. For large transfers, upload an archive to a
private staging folder and extract into the intended destination, preserving the
relative structure. Upload reviewed product/CMS files only; do not copy unrelated
archives, database dumps or environment files into public media.

Do not also run seed_manufacturer_catalogue or seed_smartliving_categories for
this fixture path. The fixture already carries the catalogue and categories.

## 7. Create private application directories on the server

In cPanel Terminal/SSH **Bash**, record the following variables. Re-enter them
after opening a new terminal session. Confirm HOME is your actual cPanel home.

```bash
export APP_ROOT="$HOME/apps/smartliving"
export RELEASE_ROOT="$APP_ROOT/current"
export PASSENGER_ROOT="$APP_ROOT/passenger"
export SHARED_ROOT="$APP_ROOT/shared"
export DOC_ROOT="$HOME/public_html/smartliving"
umask 077
mkdir -p "$RELEASE_ROOT" "$PASSENGER_ROOT" "$SHARED_ROOT/media" "$SHARED_ROOT/staticfiles" "$SHARED_ROOT/var/private_imports" "$SHARED_ROOT/var/private_documents" "$APP_ROOT/backups" "$APP_ROOT/incoming" "$APP_ROOT/logs"
```

Use the document root recorded in step 3 if it differs. Here is the intended layout:

```text
/home/ACTUAL_ACCOUNT/
  apps/smartliving/
    current/                        manage.py, apps/, config/, templates/, static/
    passenger/passenger_wsgi.py      Startup used by Setup Python App
    shared/.env                     Private production configuration
    shared/media/                   Public product and CMS images
    shared/staticfiles/             Collected CSS, JS, admin assets
    shared/var/private_imports/      Private Admin import staging
    shared/var/private_documents/    PDFs served through document permissions
    incoming/                       Private upload/import staging
    backups/                        Private backups
    logs/                           Private logs
  public_html/smartliving/
    .htaccess                       Panel-generated Passenger rules + protections
    static -> .../shared/staticfiles
    media  -> .../shared/media
```

This guide uses absolute storage settings, so source-root media/var symlinks are
not needed. Source can be replaced later while shared files remain persistent.

Upload the source ZIP and SHA256 file to incoming/ privately. In Bash:

```bash
cd "$APP_ROOT/incoming"
sha256sum -c smartliving-production.sha256
unzip -l smartliving-production.zip
```

Expected: checksum OK, paths include manage.py, apps/ and config/ without a parent
project folder. For a first install, extract with File Manager into the empty
current/ directory. Do not overwrite a populated source directory as a first-install
step. Confirm current/manage.py and current/requirements-production.txt exist.

Upload catalogue-and-content.json to incoming/ and the two file trees to their
shared destinations from step 6. Keep incoming/ private.

## 8. Register Setup Python App

cPanel > Setup Python App > Create Application:

| Field | Value |
|---|---|
| Python version | Current patched 3.12 preferred; otherwise compatible patched 3.11 |
| Application root | apps/smartliving/passenger |
| Application URL | smartliving.seas-india.com |
| URL path, if separate | / |
| Startup file | passenger_wsgi.py |
| Entry point | application |
| Mode, if offered | Production |
| Passenger log, if offered | /home/ACTUAL_ACCOUNT/apps/smartliving/logs/passenger.log |

Use this app's own virtualenv. Copy the exact activation command shown in the
panel; do not copy an environment path from another application or this example.
The generated sample app may be visible temporarily; keep Smart Living stopped
in the panel until configuration/data/static preparation is complete.

After running the exact activation command in Bash:

```bash
export VENV_BIN="${VIRTUAL_ENV:?Activate the Smart Living virtualenv first}/bin"
"$VENV_BIN/python" --version
cd "$RELEASE_ROOT"
"$VENV_BIN/python" -m pip install -r requirements-production.txt
"$VENV_BIN/python" -m pip check
"$VENV_BIN/python" -c "import django, MySQLdb, PIL; print('Django', django.get_version(), 'MySQL driver and Pillow import OK')"
```

If mysqlclient fails to build, ask support for the client development libraries,
pkg-config/build tooling or a compatible host-provided build. Shared hosting may
not allow you to install these system packages. Do not use sudo, replace the
server Python, silently change database drivers or omit the pinned package.
Proceed only after installation and import checks succeed.

## 9. Create a separate database

cPanel > MySQL Databases / Manage My Databases / Database Wizard:

1. Create a new Smart Living database.
2. Create a new database user and generate a unique password privately.
3. Assign that user privileges on the Smart Living database only, including
   privileges needed for migrations. Do not give it access to the SEAS database.
4. Record the complete prefixed names, such as ACCOUNT_smartliving; cPanel may
   truncate names, so copy exactly what the panel actually creates.
5. In phpMyAdmin, select only the new database and set its default character set
   to utf8mb4 with a host-supported collation. Check InnoDB is the default engine.
6. Use phpMyAdmin's server details or ask support for the real server version,
   hostname and port. A MySQL client binary's version does not prove the database
   server version. The ordinary port is 3306; local development port 3307 is not
   a reason to use 3307 on GoDaddy.

Do not seed or import business records yet. The target catalogue/CMS must be empty
before the first fixture import in step 12.

## 10. Generate and complete the private environment file

In Bash:

```bash
cd "$RELEASE_ROOT"
"$VENV_BIN/python" scripts/init_production_env.py --output "$SHARED_ROOT/.env"
chmod 600 "$SHARED_ROOT/.env"
```

The helper generates a random secret without printing it and refuses to overwrite
an existing file. In File Manager enable Show Hidden Files and edit this private
file. Keep its generated DJANGO_SECRET_KEY. Fill DB_NAME, DB_USER and DB_PASSWORD
with the exact production credentials. Use quoted dotenv values when needed;
do not insert secrets into terminal commands, screenshots or chat.

Confirm these values, replacing ACTUAL_ACCOUNT with your actual account:

```dotenv
DJANGO_ENV=production
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=smartliving.seas-india.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://smartliving.seas-india.com
DJANGO_SECURE_SSL_REDIRECT=True
DJANGO_SECURE_HSTS_SECONDS=3600
DJANGO_TRUST_X_FORWARDED_PROTO=False
DJANGO_DB_ENGINE=mysql
DB_HOST=localhost
DB_PORT=3306
DB_CONN_MAX_AGE=60
DJANGO_MEDIA_ROOT=/home/ACTUAL_ACCOUNT/apps/smartliving/shared/media
DJANGO_STATIC_ROOT=/home/ACTUAL_ACCOUNT/apps/smartliving/shared/staticfiles
DJANGO_PRIVATE_IMPORT_ROOT=/home/ACTUAL_ACCOUNT/apps/smartliving/shared/var/private_imports
DJANGO_PRIVATE_DOCUMENT_ROOT=/home/ACTUAL_ACCOUNT/apps/smartliving/shared/var/private_documents
```

DB_HOST/DB_PORT must follow the host's actual values. Do not literally paste
ACTUAL_ACCOUNT or leave the DB placeholders from the generated template.
Keep the generated secret stable across restarts and releases.

In the **Smart Living Python App's** Environment Variables add:

| Variable | Value |
|---|---|
| DJANGO_ENV_FILE | /home/ACTUAL_ACCOUNT/apps/smartliving/shared/.env |
| SMARTLIVING_PROJECT_ROOT | /home/ACTUAL_ACCOUNT/apps/smartliving/current |
| DJANGO_SETTINGS_MODULE | config.production |

Save. Remove stale duplicate DB/debug/host values from this app's panel environment,
if any. Existing process environment values take precedence over dotenv values.
Do not edit environment variables belonging to SEAS.

For the terminal session, also run:

```bash
export DJANGO_ENV_FILE="$SHARED_ROOT/.env"
export DJANGO_SETTINGS_MODULE=config.production
```

Do not run source .env; it is a dotenv file, not a shell script.
Run every remaining management command in the Smart Living environment and source
directory. Configuration will fail closed for invalid production settings.

## 11. Install the startup file and validate configuration

Back up the panel-generated startup file privately if present, then copy the
shipped deployment entry point:

```bash
cp "$RELEASE_ROOT/deploy/cpanel/passenger_wsgi.py" "$PASSENGER_ROOT/passenger_wsgi.py"
"$VENV_BIN/python" "$PASSENGER_ROOT/passenger_wsgi.py"
cd "$RELEASE_ROOT"
"$VENV_BIN/python" manage.py production_check --configuration-only
"$VENV_BIN/python" manage.py check
"$VENV_BIN/python" manage.py makemigrations --check --dry-run
"$VENV_BIN/python" manage.py migrate --plan
```

Expected: startup import succeeds, configuration check passes, no model/migration
drift. A successful import is not yet an HTTP launch test. The configuration-only
check verifies installed pinned packages/settings but deliberately skips business
data, migrations, asset and database checks.

## 12. Migrate and import into the empty target

Run migrations first:

```bash
"$VENV_BIN/python" manage.py migrate --noinput
"$VENV_BIN/python" manage.py migrate --check
```

Confirm the fixture target is empty:

```bash
"$VENV_BIN/python" manage.py shell -c "from apps.catalogue.models import Brand, Category, Product; from apps.cms.models import ContentPage, HomeSection, FAQ; from apps.core.models import SiteSettings; models=(Brand,Category,Product,ContentPage,HomeSection,FAQ,SiteSettings); assert not any(model.objects.exists() for model in models), 'STOP: target business tables are not empty'; print('Empty catalogue/CMS target confirmed')"
```

If that assertion fails, stop. Do not clear tables to make it pass. Review existing
data and use a stable-identifier merge instead. A fixture import can overwrite
records with matching database IDs.

Import the uploaded local fixture:

```bash
"$VENV_BIN/python" manage.py loaddata "$APP_ROOT/incoming/catalogue-and-content.json"
"$VENV_BIN/python" manage.py rebuild_product_search
"$VENV_BIN/python" manage.py seed_business_content --dry-run
"$VENV_BIN/python" manage.py seed_business_content
"$VENV_BIN/python" manage.py seed_sales_roles
"$VENV_BIN/python" manage.py createsuperuser
```

The CMS seed preserves existing page edits/publication decisions and adds missing
starter pages. It includes the solutions, services and explicitly labelled
project guides discussed in this chat. It does not invent completed installations.
The fixture carries your local CMS/homepage state; do not replace it with the seed
when you want to retain later local editorial changes.

Use a new production superuser password. Local admin accounts/password hashes are
not transferred by this selected fixture. Sales groups are created but are not
automatically assigned to users. Create approved named staff accounts later.

Check documents after copying BOTH media trees:

```bash
"$VENV_BIN/python" manage.py secure_product_documents --dry-run
```

Expected: all referenced document paths are present and non-conflicting. Current
local documents should already be private. If a legacy public PDF copy remains,
back up first, inspect the dry run, then use secure_product_documents
--remove-public-copies to copy/verify and remove those public originals. Never
publicly alias private_documents or var.

Compare catalogue, gallery, specification, document and CMS counts against local
Admin. Check representative files actually exist; a successful JSON import by
itself does not prove images/PDFs were uploaded.

## 13. Collect and publish static/media files

```bash
"$VENV_BIN/python" manage.py collectstatic --noinput
```

With DEBUG=False, Django does not serve ordinary public media for you. Apache must
serve both /static/ and /media/ using the directories configured in step 10.

Where the host supports same-account symlinks, and only if the destinations below
do not already exist:

```bash
ln -s "$SHARED_ROOT/staticfiles" "$DOC_ROOT/static"
ln -s "$SHARED_ROOT/media" "$DOC_ROOT/media"
```

If either destination exists, inspect it; do not delete/replace it automatically.
If symlinks are disallowed, ask support to configure equivalent aliases or an
approved public storage layout. A source-root media folder alone is insufficient.

The private umask used earlier protects secrets but may leave public files unreadable
by Apache. Ask the host to set the account's appropriate traversal/read permissions
or ACLs. A common same-account symlink setup uses traversal on the app/shared
ancestors and 755/644 for PUBLIC directories/files only. Do not recursively change
the private source/shared/var tree, loosen .env/private-document permissions, or
use 777. Recheck public-file permissions after later uploads/collectstatic runs.

Preserve the panel-generated .htaccess Passenger directives. Add the rules from
deploy/cpanel/public.htaccess.example to the Smart Living document root only;
do not replace the SEAS root .htaccess. Install the public-media protection file:

```bash
cp "$RELEASE_ROOT/deploy/cpanel/media.htaccess" "$SHARED_ROOT/media/.htaccess"
```

The host must permit the directives, deny script execution in media and disable
directory listings. If they cause an Apache 500, use support-approved equivalents
rather than leaving uploads executable. Check that inherited SEAS/WordPress
rewrite rules are not capturing this subdomain.

## 14. Start and perform launch acceptance

Start/Restart **only the Smart Living app** using Setup Python App. Then:

```bash
cd "$RELEASE_ROOT"
"$VENV_BIN/python" manage.py production_check
"$VENV_BIN/python" scripts/smoke_production.py --url https://smartliving.seas-india.com
```

Complete Site settings in Admin with the actual business name, phone, email,
address and public URL https://smartliving.seas-india.com. If full preflight reports
missing identity, complete it and rerun. A superuser meets the operator permission
gate, but ordinary staff should receive only approved Sales roles and staff status.

Required checks before announcing the site:

- Main SEAS site and its normal login still work.
- HTTPS certificate is valid; HTTP redirects to HTTPS without a loop.
- /health/live/ and /health/ready/ return 200 and {"status":"ok"}.
- /products/, category/search/filter pages, product detail, /solutions/, /services/
  and /projects/ render the intended content.
- CSS, JavaScript, admin styles, product images and CMS images load with DEBUG off.
- Public datasheets download through /documents/. A staff-only/hidden-product
  document cannot be downloaded anonymously; its old public media URL reveals no file.
- /.env, /manage.py, /db.sqlite3, /var/private_imports/ and backups reveal no contents.
- Log in, submit a clearly labelled launch-test enquiry with consent, and confirm
  it in /workspace/. Verify product quotation requests, survey requests, staff
  follow-ups and quotation totals/print output; a viewer cannot mutate records.
- Check phone and desktop layouts and logout. Do not treat a health 200 as proof
  of all customer workflows.
- Confirm REMOTE_ADDR represents the actual client or an appropriate host-controlled
  value. Enquiry POSTs share 10 attempts per five-minute bucket per address;
  admin-login POSTs have a separate limit of 20. A proxy address shared by everyone
  can cause unintended 429 responses. Do not solve that by trusting arbitrary
  forwarded headers; ask support for correct real-client address configuration.
- Review private application/server logs and cPanel resource usage while checking
  both sites. Local catalogue benchmarks do not establish Economy hosting capacity.

The full production check intentionally acknowledges HSTS W005/W021 because
subdomain-wide HSTS/preload are not enabled. Other preflight failures must be fixed.
The read-only smoke script does not submit forms or authenticate; the manual
workflow checks above are still required.

After successful verification, remove temporary upload/import archives from the
server's private incoming folder using File Manager, retaining the needed secured
off-host source/data backup. Never expose them with a public download URL.

## 15. Backups and scheduled housekeeping

Before launch and before every update, from the configured app environment:

```bash
"$VENV_BIN/python" manage.py backup_site --output-dir "$APP_ROOT/backups"
```

The backup includes MySQL, public media, private documents and a checksum manifest.
It deliberately excludes .env; retain an encrypted private configuration copy and
the matching source ZIP/package set separately. A backup directory containing
INCOMPLETE is not a successful backup. If mysqldump is unavailable, ask support
for its path and pass --mysqldump /actual/path/mysqldump.

Pause conflicting uploads/edits for a coordinated database/file snapshot, and do
not run schema migrations during the dump. Encrypt and copy verified backups
off-host; backups on the same account alone do not cover account loss.

Use cPanel > Cron Jobs with the account's actual **absolute** virtualenv Python
path. Do not use $VENV_BIN in cron because that shell variable is not persistent.
Replace ACTUAL_VENV and ACTUAL_ACCOUNT in these templates, and choose schedules
using the server's actual timezone:

```text
DJANGO_ENV_FILE=/home/ACTUAL_ACCOUNT/apps/smartliving/shared/.env /ACTUAL_VENV/bin/python /home/ACTUAL_ACCOUNT/apps/smartliving/current/manage.py backup_site --settings=config.production --output-dir /home/ACTUAL_ACCOUNT/apps/smartliving/backups >> /home/ACTUAL_ACCOUNT/apps/smartliving/logs/backup.log 2>&1

DJANGO_ENV_FILE=/home/ACTUAL_ACCOUNT/apps/smartliving/shared/.env /ACTUAL_VENV/bin/python /home/ACTUAL_ACCOUNT/apps/smartliving/current/manage.py clearsessions --settings=config.production >> /home/ACTUAL_ACCOUNT/apps/smartliving/logs/housekeeping.log 2>&1
```

A daily off-peak schedule is a starting point; choose backup frequency and retention
for business needs and monitor failures/disk space. Cron is not required for the
existing in-portal notification polling.

Rehearse a restore into a different private test database/app with matching code,
configuration, public media and private documents. Verify checksums and safely
inspect archive paths before extraction. Restore SQL only into the deliberately
selected test database; the backup SQL omits CREATE DATABASE/USE directives.
Verify counts, login, permissions, gallery and PDF downloads, enquiries and totals.
Do not claim recoverability until that rehearsal passes.

## 16. Updates, rollback and content changes

For code updates: take a verified backup, preserve the current release/package
set, review the migration plan, prepare the new source in a separate private
release directory, and use a maintenance window for migrations/activation. Keep
shared/.env, media, private documents and backups persistent. Install the tested
dependencies, run migrations, collectstatic, preflight, restart only Smart Living,
and repeat HTTP/browser checks. Do not recopy your local fixture over a live
database that now contains production edits and enquiries.

For later product/content additions, use the Admin stable-key import tools only
for the data types they support. Copy matching media first and review the preview.
The existing generic media ZIP/import path is not a complete transfer of all
catalogue relationships/private documents. See BUSINESS_CONTENT_DEPLOYMENT.md for
CMS page export/import, and do not confuse it with a complete catalogue merge.

For rollback: a compatible code-only release can be restored with its matching
dependencies while keeping shared storage. If a migration/data change is
incompatible, restore the matching code/database/files into a recovery app first.
Reconcile enquiries and edits received since the snapshot before switching data.
Do not guess reverse migrations, wipe the database or overwrite live enquiries.
If this is a failed first launch, keep Smart Living stopped while fixing it;
leave the existing SEAS deployment intact.

## Troubleshooting

| Symptom | Check / action |
|---|---|
| SEAS page opens on Smart Living | Separate subdomain document root, app URL binding and inherited .htaccess rules |
| Passenger 500 / app cannot start | This app's log, absolute source path, interpreter, DJANGO_ENV_FILE, pinned packages and DB configuration |
| Invalid production configuration | Fill actual secret/database/host/path values; remove stale panel overrides; do not enable DEBUG |
| mysqlclient build fails | Support-provided client libraries/build tools or a compatible environment |
| Database server unsupported | Confirm server version; provision a supported database before migrating |
| MySQL access denied | Full cPanel-prefixed credentials and privileges on only the Smart Living DB |
| 400 / DisallowedHost | Exact Smart Living hostname in ALLOWED_HOSTS; use the hostname rather than direct IP access |
| CSRF 403 | Valid HTTPS, exact trusted origin, correct host and browser cookies; retain CSRF protection |
| Redirect loop | Trusted HTTPS detection/proxy configuration; do not disable secure cookies |
| CSS/images missing or forbidden | collectstatic, storage settings, Apache aliases/symlinks, ownership/traversal and public file read permissions |
| Missing PDFs | Correct private root/file paths, document visibility and product publication; never expose private storage to fix it |
| Empty solutions/services/projects | Current code/migration plus CMS fixture or seed_business_content; inspect publication flags |
| Unexpected 429 for several customers | Proxy/client-address configuration; confirm shared-address behavior with support |
| 503 / resource limit hit | cPanel resource logs, worker/process/memory/CPU and DB limits; the plan may need more capacity |
| Backup fails | mysqldump path/permissions, disk quota, private root and absence of INCOMPLETE |

## Evidence and references

Local code, settings, commands and release inputs were inspected for this guide.
The selected catalogue/CMS fixture was exported with Windows UTF-8 mode and
successfully imported into an isolated empty SQLite database: 20,948 records
across 11 populated models. All referenced source media/private files existed.
The source database was read only during that check. Four production-tool tests,
Django checks and migration-drift checks passed. The source ZIP passed integrity,
required-file and checksum validation. This verifies the local export/import
shape, not GoDaddy MySQL, Linux permissions or live Passenger compatibility.
No GoDaddy credentials, live DNS/certificates, panel values or hosting limits have
been verified from this chat. Use the acceptance steps as launch gates rather
than interpreting this document as a guarantee that no hosting error can occur.

- [GoDaddy supported components](https://www.godaddy.com/en-uk/help/article/which-components-does-my-hosting-support-5614?locale=en)
- [GoDaddy SSH](https://www.godaddy.com/en-ca/help/enable-ssh-for-my-web-hosting-cpanel-account-16102)
- [GoDaddy integrated SSL](https://www.godaddy.com/help/activate-an-integrated-ssl-32040)
- [cPanel subdomains](https://support.cpanel.net/hc/en-us/articles/360052780313-How-to-create-a-subdomain)
- [cPanel Python WSGI background](https://docs.cpanel.net/knowledge-base/web-services/how-to-install-a-python-wsgi-application/) — its Application Manager interface differs from your confirmed Setup Python App; use your panel's exact environment controls.
- [Django Python compatibility](https://docs.djangoproject.com/en/5.2/faq/install/)
- [Django database compatibility](https://docs.djangoproject.com/en/5.2/ref/databases/)
- [Django deployment checklist](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/)
