# Smart Living one-command GitHub updates

> **Current hosting instructions (16 October 2026):** follow [the working cPanel configuration](../docs/CPANEL_WORKING_CONFIGURATION.md). The owner reported the site working after replacing the recursive Passenger loader and using real public static/media directories. The older symlink layout below is not the layout to reapply on this account. The updated deployer supports these public roots; follow [the automation setup](../docs/DEPLOYMENT_AUTOMATION.md) before its first run.

Repository selected for this project: **git@github.com:surajgupta57/smartliving.git**.
The example uses **main**; confirm the intended branch before configuring the server.
Repository access/default branch could not be verified from this session.

This is the independent Smart Living deployer. It does not use the SEAS database,
repository, credentials, virtualenv or deployment directories. Nothing in this
folder has been run against GoDaddy from this chat.

After the one-time setup below, routine updates are:

```bash
# Activate the Smart Living virtualenv using the command shown by cPanel.
python /home/ACTUAL_ACCOUNT/apps/smartliving/deployer/deploy.py --dry-run
python /home/ACTUAL_ACCOUNT/apps/smartliving/deployer/deploy.py
```

Replace ACTUAL_ACCOUNT with the real account name. The private deploy.json selects
the repository/branch, interpreter and HTTPS origin, so no passwords are placed
on a command line. GitHub pushes do not trigger a deployment automatically; run
this command after committing and pushing the intended changes.

## What is automated

1. Validate the existing managed app and HTTPS readiness/bootstrap protocol.
2. Clone the selected GitHub branch into a new timestamped release and pin its SHA.
3. Reject tracked environment files, databases, storage directories and symlinks.
4. Enable maintenance, wait for existing requests to drain, and back up MySQL,
   public media and private documents using the existing backup command.
5. Install pinned production packages, check requirements, run Django and
   production configuration checks, and reject model/migration drift.
6. Run committed migrations and verify none remain pending. Collect static into
   the new release, leaving the old release's manifest/assets intact.
7. Run full production preflight, atomically switch current, and restart Passenger.
8. Require HTTPS readiness from the exact deployed Git SHA, then reopen the app.

Products, enquiries, quotations, uploaded files and shared/.env remain persistent.
The deployer never runs loaddata, replaces your catalogue or auto-restores SQL.
CMS seed/import and product-search rebuilds are separate deliberate operations
when a release requires them. No automatic release/backup deletion is performed.
Monitor disk/inodes and archive or remove reviewed old releases/backups manually;
retain current, the rollback target and verified off-host backups.

## One-time setup on the hosting account

### A. Complete the first launch prerequisites

Use [the GoDaddy launch guide](../docs/GODADDY_CPANEL_LAUNCH.md) for the subdomain,
SSL, separate Python App, supported database, installed production dependencies,
private shared/.env, initial migrations/data import, public media and first
successful application preflight. This deployer automates updates to that
configured app; it does not provision DNS, certificates, databases or cPanel apps.

Use the same paths as that guide:

```text
/home/ACTUAL_ACCOUNT/apps/smartliving/
  deployer/                  Stable deploy.py and private deploy.json
  passenger/                 Stable passenger_wsgi.py and tmp/restart.txt
  shared/.env                Persistent private production settings
  shared/media/              Persistent public images
  shared/var/                Persistent private imports/documents
  releases/<timestamp>/      Versioned source and that release's staticfiles/
  current -> releases/...    Atomic active release link
  backups/                   Private MySQL/media/document snapshots
  logs/                      Private command logs and historical deployment state
  maintenance.json           Temporary private gate token, never publicly aliased
```

The stable cPanel **Application root remains apps/smartliving/passenger**. Do not
register current as the application root or cPanel can associate its virtualenv
with changing release paths. Set the panel DJANGO_ENV_FILE to shared/.env and
SMARTLIVING_PROJECT_ROOT to the absolute .../smartliving/current path. Do not
set duplicated DB/password/storage values in the panel; dotenv must be the single
configuration source for the app and deployment commands.

### B. Use a dedicated GitHub repository

The repository root must contain manage.py, apps/, config/, templates/, static/,
requirements-production.txt and the committed migrations. Only the intended
Smart Living code should be in this repository. If your local directory belongs
to a larger parent repository, create a separate clean Smart Living code checkout
for GitHub rather than pushing unrelated projects or private data.

Review tracked files before the first push: exclude .env, deploy.json, databases,
public/private uploads, backup archives, output/, tmp/ and virtualenvs. Include
.env.production.example and deploy/deploy.example.json only as templates. Ignore
rules do not untrack a secret already committed; review history and rotate any
exposed credential before publishing. Do not force-push or replace an existing
repository based only on this example.

The deployer uses git@github.com:OWNER/REPOSITORY.git and a noninteractive,
**read-only repository deploy key**. It does not need a GitHub write token.
Generate a distinct SSH key on the host and add its public key in the Smart Living
repository > Settings > Deploy keys. Leave Allow write access unchecked. Keep
the private key on the server with restricted permissions.

In hosting Bash, if this dedicated key filename does not already exist:

```bash
mkdir -p "$HOME/.ssh"
ssh-keygen -t ed25519 -f "$HOME/.ssh/smartliving_deploy" -C "smartliving-production"
cat "$HOME/.ssh/smartliving_deploy.pub"
```

Never overwrite an existing SEAS key. Copy only the displayed **.pub** public key
into GitHub. A passphrase-protected key must be unlocked in an SSH agent for
noninteractive deployment. After verifying GitHub's published host fingerprint,
use an initial SSH connection to establish its known_hosts entry:

```bash
ssh -i "$HOME/.ssh/smartliving_deploy" -o IdentitiesOnly=yes -T git@github.com
```

GitHub reports successful authentication without shell access (that SSH test may
exit with status 1 even after successful authentication). Confirm the repository
exists, this key has read access, and the selected branch is the actual release
branch before deploying.

Because SEAS also uses GitHub, use the explicit ssh_key path in deploy.json for
Smart Living. The deployer selects that identity with IdentitiesOnly=yes for
the clone as well as later Git commands. It enforces BatchMode and
StrictHostKeyChecking and never disables host verification. Verify GitHub's
published SSH host-key fingerprint before adding/accepting its known_hosts entry.
Do not overwrite the SEAS SSH config/key. A missing/passphrase-locked key will
stop the operation unless you have deliberately unlocked it in a suitable agent.

Read [GitHub's deploy-key instructions](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/managing-deploy-keys).

### C. Install the stable tools

Upload deploy/deploy.py and deploy/deploy.example.json from this release into
the private .../smartliving/deployer/ directory. Copy the example to deploy.json,
fill the actual values and set mode 600. Keep deploy.py outside current so a
release switch or a broken new source does not remove the running deploy tool.

```json
{
  "app_root": "/home/ACTUAL_ACCOUNT/apps/smartliving",
  "python": "/ACTUAL/CPANEL/VIRTUALENV/bin/python",
  "repository": "git@github.com:surajgupta57/smartliving.git",
  "ssh_key": "/home/ACTUAL_ACCOUNT/.ssh/smartliving_deploy",
  "branch": "main",
  "origin": "https://smartliving.seas-india.com",
  "drain_seconds": 10,
  "health_attempts": 12
}
```

Use the exact virtualenv interpreter shown by Setup Python App, not the example
path. Set the branch to your actual release branch. The deploy config contains
no database password; the app reads shared/.env. Do not change the paths or
repository of the existing SEAS deployer.

Install **this release's** deploy/cpanel/passenger_wsgi.py into the stable
passenger/ directory, backing up the existing startup file privately. Restart
only Smart Living once through cPanel. It must serve these response headers at
/health/ready/ before the deployer will update it:

```text
X-SmartLiving-Deploy-Protocol: 1
X-SmartLiving-Release: manual
```

The release header becomes a full Git SHA on subsequent managed releases. The
value is captured when each worker starts, allowing the deployer to reject a
healthy response from a worker still running older code.

### D. Legacy alias layout only: prepare release-specific static files

For this repaired hosting account, use [DEPLOYMENT_AUTOMATION.md](../docs/DEPLOYMENT_AUTOMATION.md) instead of sections D/E below. With public_root configured, leave real public static/media directories unchanged; candidate static files are staged privately and copied into public static under maintenance. Omit public_root only for the original host-approved alias layout.


Earlier manual instructions used shared/staticfiles. Automated releases require
each release's own manifest/assets so preparing a candidate cannot break the
active website. In shared/.env change only the static setting to:

```dotenv
DJANGO_STATIC_ROOT=/home/ACTUAL_ACCOUNT/apps/smartliving/current/staticfiles
```

Keep these existing persistent paths exactly:

```dotenv
DJANGO_MEDIA_ROOT=/home/ACTUAL_ACCOUNT/apps/smartliving/shared/media
DJANGO_PRIVATE_IMPORT_ROOT=/home/ACTUAL_ACCOUNT/apps/smartliving/shared/var/private_imports
DJANGO_PRIVATE_DOCUMENT_ROOT=/home/ACTUAL_ACCOUNT/apps/smartliving/shared/var/private_documents
```

If current/staticfiles is absent, the adoption command copies the existing
shared/staticfiles into the baseline source before moving it. If it is already
a real directory, preserve it. If it is a symlink from an earlier setup, stop,
back up and deliberately convert it to a real directory containing the same
assets before adoption; the script refuses to alter that symlink automatically.
Do not remove its target or delete assets to satisfy the command.

Leave the public /static/ mapping pointing at the existing shared/staticfiles
while performing adoption below. Do not switch it to a missing directory, and
do not restart solely for this .env change before adoption has prepared the
baseline static files. Adoption copies the baseline assets and restarts the app.
Keep /media/ pointing to shared/media throughout.

Have the host ensure Apache can traverse the app root and release paths. The
deployer grants traversal to releases/release roots and read access only to
collected static; private source files, environment settings and shared/var stay
restricted.

### E. Adopt an existing manual installation once

In cPanel Terminal, activate Smart Living's virtualenv, then run:

```bash
python /home/ACTUAL_ACCOUNT/apps/smartliving/deployer/deploy.py --dry-run
python /home/ACTUAL_ACCOUNT/apps/smartliving/deployer/deploy.py --adopt-current
```

Adoption checks readiness, enables maintenance, backs up the existing database
and files, preserves the manual source under releases/manual-<timestamp>, replaces
current with a symlink and restarts/verifies the same app. It does not delete the
original source or import data. Existing current symlinks must point directly
to this app's releases/ directory. If adoption fails, review the private logs and
maintenance marker before using --adopt-current --resume. Do not remove the gate
without inspecting the failure.

After adoption succeeds, change only the Smart Living /static/ Apache alias or
public symlink to point to .../smartliving/current/staticfiles. Preserve the old
link/directory privately until verification passes. Verify CSS, public images and
readiness before the first GitHub update. Candidate releases retain prior hashed
assets so already-open pages can still fetch them after activation; account for
those accumulated public assets when monitoring disk usage.

### F. Run the first GitHub update

```bash
python /home/ACTUAL_ACCOUNT/apps/smartliving/deployer/deploy.py
python /home/ACTUAL_ACCOUNT/apps/smartliving/deployer/deploy.py --status
python /home/ACTUAL_ACCOUNT/apps/smartliving/deployer/deploy.py --health
```

Check real browser workflows after the first update: SEAS still works; Smart
Living product images/PDFs, CSS, login, enquiries, surveys and quotation flows work.
Health checks do not replace browser acceptance or a backup-restore rehearsal.

## Supported commands and recovery

```bash
python deploy.py --dry-run
python deploy.py --status
python deploy.py --health
python deploy.py --backup
python deploy.py
python deploy.py --allow-dependency-change
python deploy.py --resume
python deploy.py --rollback --schema-compatible
```

Use the absolute stable script path when outside its directory. --config can
select an alternate private JSON path. --dry-run validates the configured paths
and bootstrap file, prints the plan, and performs no Git/network/database writes
or commands. It does not prove SSH authentication, database access or live readiness.
--status reads local state without contacting GitHub or changing anything.
Mutating operations use an exclusive Linux file lock released by the OS if the
deployer exits; the existence of deployment.lock alone does not mean it is locked.

**Dependency changes:** if requirements-production.txt changed, the script stops
before maintenance and asks for --allow-dependency-change. Review the change first.
Packages use the stable cPanel virtualenv; an interrupted package upgrade can
affect both source releases. After such a failure maintenance stays enabled until
the package state is repaired and the app passes checks. It does not silently
downgrade the environment or reopen old code.

**Migrations:** before invoking migrate, the script marks the attempt as potentially
schema-changing. If migrate or a later stage fails, it retains maintenance, code,
backup and logs for diagnosis. Even when no migrations were pending, this is a
conservative failure boundary. It never automatically restores SQL or reverses
migrations, which could discard new data or fail after partially committed MySQL
DDL. Fix the release and push it, then use --resume to deploy a new candidate. A
rerun still runs migrate and migrate --check; an already-active SHA is not skipped.

Before migrations/dependency changes, a rejected candidate leaves the prior code
active and can reopen it after its readiness check. A failed resumed attempt
keeps maintenance because an earlier operation may already have changed schema.

**Rollback:** --rollback requires an explicit --schema-compatible acknowledgement.
Use it only after checking the prior source supports the current database and
installed packages. The tool backs up current data, checks the previous release,
switches code and verifies its SHA. It never restores an older database/uploads.
If installed dependencies differ, restore the compatible package set deliberately
under maintenance before retrying. Historical state files remain in private logs.

The deployer does not offer automatic backup retention or automatic data restore.
For incompatible recovery, restore a verified snapshot with matching code/config
into a separate recovery app/database, reconcile later enquiries, then plan the
switch. Preserve the only recoverable copies.

**Maintenance:** the stable Passenger wrapper responds 503/no-store to new app
requests while the private gate exists. Only an authenticated GET/HEAD to the exact
readiness endpoint can bypass it; tokens are never sent through redirects or
printed. Static/media files served by Apache remain accessible. The configured
drain delay is not a guarantee that all long requests, background jobs or external
writers have stopped; pause those and choose an appropriate maintenance window.

## Validation boundary

Local automated tests cover ordering, dry-run behaviour, environment isolation,
path/config rejection, failure gates, schema acknowledgement and the WSGI gate.
They do not prove Linux flock/atomic symlinks, GitHub keys, the host's Passenger
restart timing, real certificates or live MySQL migrations. Test the first server
deployment during a controlled window, retain backups and verify the browser flows.

The stable deployer/bootstrap are upgraded deliberately from a reviewed source
release; a normal app update does not overwrite the script currently performing
the deployment. No SEAS deployment code or configuration was modified.
