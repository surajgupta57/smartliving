# Smart Living: working cPanel configuration and operations

Updated 16 October 2026 after the owner reported the website working following the startup and asset fixes below. This records the working manual hosting layout; it does not certify backups, restore, all business workflows or hosting security checks.

Use this guide for the current account. Older symlink instructions in the other launch guides are alternatives for hosts that permit them, not the layout to reapply here. Commands below are **Bash in cPanel Terminal**. Activate the separate Smart Living virtualenv using the exact activation command displayed by Setup Python App. Stop on any command error. Preserve the separate SEAS site and database.

## 1. Paths and cPanel registration

| Purpose | Current value |
|---|---|
| Website | https://smartliving.seas-india.com |
| Source | /home/a7bc3w2x98u9/apps/smartliving/current |
| Python App root | apps/smartliving/passenger |
| Startup / entry point | passenger_wsgi.py / application |
| Public document root | /home/a7bc3w2x98u9/public_html/smartliving |
| Collected static | /home/a7bc3w2x98u9/public_html/smartliving/static (real directory) |
| Uploaded images | /home/a7bc3w2x98u9/public_html/smartliving/media (real directory) |
| Private documents | /home/a7bc3w2x98u9/apps/smartliving/shared/var/private_documents |
| Private imports | /home/a7bc3w2x98u9/apps/smartliving/shared/var/private_imports |

At the start of each activated Terminal session:

```bash
export APP_ROOT="$HOME/apps/smartliving"
export RELEASE_ROOT="$APP_ROOT/current"
export PASSENGER_ROOT="$APP_ROOT/passenger"
export DOC_ROOT="$HOME/public_html/smartliving"
export VENV_BIN="${VIRTUAL_ENV:?Activate the Smart Living virtualenv first}/bin"
cd "$RELEASE_ROOT"
```

Keep source, .env, database exports, archives, logs and private files outside public_html. Do not change the subdomain document root to current/. Do not use permissions 777.

## 2. Production settings used by both Terminal and Passenger

The application reads current/.env by default. If using a different private file, configure DJANGO_ENV_FILE to its absolute path in cPanel and export the same path in Terminal and cron. Do not source a dotenv file as Bash.

Configure these values privately in that file; preserve the existing production secret and database credentials:

```dotenv
DJANGO_ENV=production
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=smartliving.seas-india.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://smartliving.seas-india.com
DJANGO_SECURE_SSL_REDIRECT=True
DJANGO_DB_ENGINE=mysql
DJANGO_STATIC_ROOT=/home/a7bc3w2x98u9/public_html/smartliving/static
DJANGO_MEDIA_ROOT=/home/a7bc3w2x98u9/public_html/smartliving/media
DJANGO_PRIVATE_IMPORT_ROOT=/home/a7bc3w2x98u9/apps/smartliving/shared/var/private_imports
DJANGO_PRIVATE_DOCUMENT_ROOT=/home/a7bc3w2x98u9/apps/smartliving/shared/var/private_documents
```

Also supply DJANGO_SECRET_KEY (unique random secret of at least 50 characters), DB_NAME, DB_USER, DB_PASSWORD, DB_HOST and the host-provided DB_PORT. Never copy the local development port 3307 without hosting confirmation. Protect the private file with chmod 600.

**cPanel environment variables override the file.** Correct stale panel entries, particularly DJANGO_SECRET_KEY, DJANGO_STATIC_ROOT and DJANGO_MEDIA_ROOT. Panel-only variables may not appear in an activated Terminal session. Ensure CLI, cron and Passenger all select the same production file and values before performing migrations, imports or backups. Never print secrets or use diffsettings for troubleshooting.

For a fresh installation only, scripts/init_production_env.py --output PATH generates a private template without printing its secret and refuses to overwrite an existing file. Fill its placeholders and set the paths above before startup. Do not regenerate an established site's secret during updates. Restart the Python App after settings changes.

Check effective public roots without exposing credentials:

```bash
"$VENV_BIN/python" manage.py shell --settings=config.production -c "from django.conf import settings as s; print('STATIC_ROOT:', s.STATIC_ROOT); print('MEDIA_ROOT:', s.MEDIA_ROOT)"
```

## 3. Correct Passenger startup

The panel-generated loader called imp.load_source('wsgi', 'passenger_wsgi.py'), loading itself repeatedly and ending in RecursionError. Replace the entire generated loader with this project's bootstrap; merely changing imp to importlib does not fix self-loading.

```bash
test -f "$RELEASE_ROOT/manage.py"
test -f "$RELEASE_ROOT/deploy/cpanel/passenger_wsgi.py"
mkdir -p "$APP_ROOT/backups/startup"
chmod 700 "$APP_ROOT/backups/startup"
```

If an existing startup file is present, back it up privately before copying:

```bash
cp -p "$PASSENGER_ROOT/passenger_wsgi.py" "$APP_ROOT/backups/startup/passenger_wsgi-$(date +%Y%m%d-%H%M%S).py"
cp "$RELEASE_ROOT/deploy/cpanel/passenger_wsgi.py" "$PASSENGER_ROOT/passenger_wsgi.py"
"$VENV_BIN/python" "$PASSENGER_ROOT/passenger_wsgi.py"
```

On a new app with no existing startup file, skip only the backup command. Successful import exits without a traceback. The bootstrap selects config.production and defaults to ../current relative to passenger/. If the source is elsewhere, configure SMARTLIVING_PROJECT_ROOT consistently. Use cPanel Restart after the import succeeds. An import alone does not prove database or HTTP readiness.

## 4. Public static and media without symlinks

Apache returned AH00037 (symbolic link not allowed or target inaccessible); CSS and an existing product image returned 403. Real directories under the confirmed document root resolved the reported symptoms. Retain this layout.

For a fresh installation, create real directories with public traversal permissions:

```bash
mkdir -p "$DOC_ROOT/static" "$DOC_ROOT/media"
chmod 755 "$DOC_ROOT/static" "$DOC_ROOT/media"
cp "$RELEASE_ROOT/deploy/cpanel/media.htaccess" "$DOC_ROOT/media/.htaccess"
chmod 644 "$DOC_ROOT/media/.htaccess"
"$VENV_BIN/python" manage.py collectstatic --noinput --settings=config.production
```

Only run those commands after confirming static and media are not symlinks. For the already repaired site, do not recreate links or recopy old shared/media over newer uploads.

For an unrepaired older installation: pause uploads, back up the actual active media, inspect ls -ld for each public path, and confirm its target. Remove only a confirmed symlink with unlink, which preserves its target; never recursively delete it. Create the replacement real directory, install media.htaccess before exposing uploads, copy approved public images from shared/media preserving relative names, and reapply media.htaccess after copying. Do not copy private product documents, imports, .env or backups into public media. Review conflicts rather than merging over a populated destination. During this one-time transfer only, set copied public directories to 755 and ordinary public files to 644. Update the permanent production roots in section 2 before collecting static and restarting.

Public media must deny script execution and directory listing. Retain deploy/cpanel/media.htaccess; preserve cPanel Passenger directives in the document-root .htaccess. If the host rejects these directives, request equivalent host protections instead of deleting them without replacement.

collectstatic copies CSS, JavaScript and bundled assets, **not uploaded product images**. Transfer approved uploads separately, retaining paths such as media/products/manufacturer_seed/FILENAME.webp. New uploads must go directly to the public MEDIA_ROOT. Old shared/media is no longer the active upload location once this configuration is applied.

## 5. Routine manual update

1. Pause writes as needed and back up the active database, media, private documents, private settings and previous matching code. Preserve public static/media during source replacement.
2. Upload the reviewed clean source under current/, preserving its private .env and persistent private storage. Never replace the production database with a local database. Do not upload a full local project containing secrets.
3. Activate the Smart Living environment, set section 1 variables, and confirm section 2 roots. Install the release's tested packages with python -m pip install -r requirements-production.txt, then python -m pip check.
4. Run the commands below one at a time, stopping on errors. Review migration plans before applying them. Back up the startup file before installing the release's bootstrap as described in section 3.

```bash
"$VENV_BIN/python" manage.py production_check --configuration-only --settings=config.production
"$VENV_BIN/python" manage.py migrate --plan --settings=config.production
"$VENV_BIN/python" manage.py migrate --noinput --settings=config.production
"$VENV_BIN/python" manage.py rebuild_product_search --settings=config.production
"$VENV_BIN/python" manage.py seed_sales_roles --settings=config.production
"$VENV_BIN/python" manage.py collectstatic --noinput --settings=config.production
"$VENV_BIN/python" "$PASSENGER_ROOT/passenger_wsgi.py"
"$VENV_BIN/python" manage.py production_check --settings=config.production
```

Restart Smart Living in cPanel. Run python scripts/smoke_production.py --url https://smartliving.seas-india.com and inspect homepage, admin, workspace, product images and a new authorised image upload. Do not rerun initial catalogue/CMS imports, createsuperuser or secret generation on routine updates. For older public document migrations, follow the secure_product_documents procedure in PRODUCTION_LAUNCH.md before reopening traffic.

**One-command updates are now supported with public_root configured.** Follow [DEPLOYMENT_AUTOMATION.md](DEPLOYMENT_AUTOMATION.md) for the one-time installation and adoption before using deploy/deploy.py. Keep these real public static/media directories; do not revert to the older symlink layout.

## 6. Backups and rollback

```bash
"$VENV_BIN/python" manage.py backup_site --output-dir "$APP_ROOT/backups" --settings=config.production
```

The command uses effective settings.MEDIA_ROOT, so with section 2 it archives public_html/smartliving/media, not the now-stale shared/media copy. Confirm CLI settings before every backup and configure cron with the same private environment file. The command also backs up MySQL and private documents. Keep private imports, settings, code and startup configuration separately if required; the command does not archive those. Keep all backups outside public_html, encrypt copies off-host, monitor failures and rehearse restoration into a separate database/app before claiming recoverability.

Preserve original shared uploads until a verified backup and restore establish the new location. A compatible code rollback must preserve current media, static root settings, private storage and credentials; recollect matching static files. Schema-incompatible rollback requires matching code/database/files restored to an isolated recovery app, with reconciliation of enquiries received since backup before switching traffic.

## 7. Verification and troubleshooting

```bash
curl -I https://smartliving.seas-india.com/static/css/site.css
curl -I https://smartliving.seas-india.com/media/products/manufacturer_seed/7bc302c25a0dadad71e83f663a6352b686a8ab51dc02a03aab9c8e6000673e84.webp
curl -I https://smartliving.seas-india.com/health/ready/
```

Expect 200 for existing public assets and readiness with a healthy database. Confirm appropriate CSS/image content types, rather than an HTML error page. Hard-refresh with Ctrl+Shift+R after repairs. If browser caching persists, inspect the actual response before purging only affected CDN URLs.

| Symptom | Diagnosis and action |
|---|---|
| Passenger generic failure | Import the installed startup using the app virtualenv; inspect the newest private Passenger log and cPanel Metrics > Errors. |
| RecursionError with repeated passenger_wsgi.py | Generated startup loads itself; install the shipped bootstrap. |
| DJANGO_SECRET_KEY ImproperlyConfigured | Missing/placeholder secret or wrong env file; inspect private configuration and stale cPanel overrides. Keep debug off. |
| Unstyled page | Check collectstatic output, effective STATIC_ROOT and public URL status. |
| Asset 403 / AH00037 | Inspect symlinks and parent traversal permissions; use this real-directory layout. Never chmod the account tree recursively. |
| Image 404 | Confirm the exact relative filename under active MEDIA_ROOT; transfer missing approved uploads. collectstatic cannot fix it. |
| Old images work, new uploads fail | Check Passenger's effective MEDIA_ROOT and writable ownership; stale panel values may override the file. |
| 500 after adding .htaccess | Ask the host which directive is rejected and obtain equivalent media protections. |

Finally verify enquiries, staff access, quotations, public/private document permissions and denied access to private paths using the launch acceptance checklist in PRODUCTION_LAUNCH.md. The owner's report that the site runs properly confirms the reported visible fix, not every acceptance item.
