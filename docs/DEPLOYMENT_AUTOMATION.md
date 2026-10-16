# Smart Living: one-command GitHub deployment

Prepared 16 October 2026 for the working cPanel account. The deployer now supports **real** public_html/smartliving/static and media directories. It does not replace them with symlinks. The only managed symlink is private apps/smartliving/current, used by Python, not by Apache to serve assets.

After the one-time setup, commit and push reviewed code to the selected GitHub branch, then run in the activated Smart Living environment:

```bash
python "$HOME/apps/smartliving/deployer/deploy.py"
```

This is a manually triggered automated deployment, not an installed GitHub push webhook or background monitor. No server credentials or GitHub access were available during local development; server setup and the first real deployment must be verified on hosting.

## What the command handles

It checks HTTPS readiness, fetches the selected branch into a private release, rejects tracked secrets/storage/databases, enables maintenance, drains requests, backs up MySQL/media/private documents, validates dependencies and Django, applies committed migrations, stages static files privately, runs production preflight, publishes assets into the real public static directory, atomically switches the private current pointer, restarts Passenger and verifies the exact Git SHA over HTTPS before reopening traffic. Existing hashed assets remain available. It never deletes customer uploads, loads fixtures, resets the database or generates a new production secret.

When the fetched SHA is already active, it skips maintenance, backups and database changes. Unchanged requirements skip pip install (pip check still runs). A changed requirements-production.txt requires explicit --allow-dependency-change after review. First deployment needs hosting time for backups and checks; no fixed runtime is promised.

## 1. Install the new tools once

Back up your existing code and private configuration first. Upload/extract the supplied smartliving-deployment-tools.zip **into apps/smartliving/current/**, preserving its deploy/ and docs/ folders. It contains deployment tools and documentation only, no application data, credentials or database. Alternatively upload these source files at their matching paths:

- deploy/deploy.py
- deploy/setup_public.py
- deploy/cpanel/passenger_wsgi.py
- deploy/cpanel/media.htaccess
- docs/DEPLOYMENT_AUTOMATION.md

Commit and push the updated deploy/deploy.py and the rest of the reviewed application code to your GitHub release branch before the first automated deployment. The tools ZIP is not the application release.

Activate the **Smart Living** virtualenv with cPanel's exact activation command. Confirm that the current private .env contains the real existing secret and database values. If those values exist only in the panel, privately copy them into current/.env first; never paste them into chat. The script will not generate replacements.

Confirm the actual release branch on GitHub. The commands below use main; change it if your selected branch differs:

```bash
cd "$HOME/apps/smartliving/current"
python deploy/setup_public.py --branch main
```

The installer backs up the previous private environment and Passenger bootstrap, creates shared/.env retaining credentials, sets the public static/media paths, installs stable tools under apps/smartliving/deployer and records the active virtualenv interpreter. It preserves public uploads. It refuses to replace an existing deploy.json; for an existing automated installation, back up its config and adapt public_root using deploy/deploy.example.json instead of rerunning setup. Retain existing shared/var private storage; stop if it is missing.

In **cPanel > Setup Python App > Smart Living**, set:

```text
DJANGO_ENV_FILE=/home/a7bc3w2x98u9/apps/smartliving/shared/.env
SMARTLIVING_PROJECT_ROOT=/home/a7bc3w2x98u9/apps/smartliving/current
```

After confirming shared/.env contains all production settings, remove stale duplicated DJANGO_/DB_ environment entries in the panel (retain DJANGO_ENV_FILE). SMARTLIVING_PROJECT_ROOT stays as shown. Do not remove unrelated hosting variables. This ensures Passenger and CLI use identical database, secret and storage values. Keep the Python App root apps/smartliving/passenger, entry point application and the public document root unchanged. **Restart Smart Living in cPanel**, and confirm the homepage still works before proceeding.

## 2. Allow read-only access to the Smart Living GitHub repository

Use the dedicated Smart Living deploy key, not a SEAS key. If this key does not already exist:

```bash
mkdir -p "$HOME/.ssh"
chmod 700 "$HOME/.ssh"
ssh-keygen -t ed25519 -f "$HOME/.ssh/smartliving_deploy" -C "smartliving-production"
cat "$HOME/.ssh/smartliving_deploy.pub"
```

Do not overwrite an existing key. Add only the .pub text in the Smart Living repository > Settings > Deploy keys. Leave write access unchecked. A passphrase requires an unlocked SSH agent when deploying; the deployer runs noninteractively. Keep the private key on the server, never in GitHub or chat.

Connect once and verify GitHub's host fingerprint against its official documentation before accepting it:

```bash
ssh -i "$HOME/.ssh/smartliving_deploy" -o IdentitiesOnly=yes -T git@github.com
```

A successful GitHub SSH greeting may exit with status 1 because no shell is offered. The deployer enforces StrictHostKeyChecking and uses only this configured identity. Repository access, branch existence and host support for outbound SSH remain server prerequisites.

Check the nonsecret private deployer config in cPanel File Manager:

```text
/home/a7bc3w2x98u9/apps/smartliving/deployer/deploy.json
```

It must name your actual repository and branch, the Smart Living interpreter and public_root=/home/a7bc3w2x98u9/public_html/smartliving. It contains no database password. Both public directories must be real directories; media/.htaccess must retain upload protections. Keep deploy.json and shared/.env private (600).

## 3. Adopt the existing manual source once

```bash
python "$HOME/apps/smartliving/deployer/deploy.py" --dry-run
python "$HOME/apps/smartliving/deployer/deploy.py" --adopt-current
```

Dry-run checks configuration/filesystem prerequisites without Git/network/database mutations; it is not proof of GitHub or database connectivity. Adoption performs readiness and backup checks, snapshots actual public static assets into the baseline, preserves the old source under releases/manual-TIMESTAMP, and creates the private current link. Apache's real static/media directories stay in place. Confirm readiness, CSS and images afterwards. If adoption fails, inspect the private log/state before --adopt-current --resume; do not delete the maintenance gate to bypass a failure.

## 4. Routine deploy after a push

```bash
python "$HOME/apps/smartliving/deployer/deploy.py"
python "$HOME/apps/smartliving/deployer/deploy.py" --status
python "$HOME/apps/smartliving/deployer/deploy.py" --health
```

No separate migrate, collectstatic or cPanel restart is normally needed. Review business workflows after the first update and meaningful code changes. CMS seeds, catalogue imports and search-index rebuilds remain deliberate release-specific operations; the deployer does not import or replace business data. The stable deployment tool and bootstrap are deliberately not overwritten by candidate code; install reviewed tool/bootstrap changes separately with private backups.

For reviewed dependency changes:

```bash
python "$HOME/apps/smartliving/deployer/deploy.py" --allow-dependency-change
```

Do not schedule unattended runs until a real deployment and restore rehearsal succeed. A push alone does not deploy. The command uses one shared virtualenv; failures after dependency/schema changes conservatively keep maintenance enabled instead of guessing rollback compatibility.

## 5. Failure recovery and rollback

Inspect apps/smartliving/logs/deploy-*.log and deployment-state.json privately. Status shows the previous/candidate release and whether migrations started. Do not share logs containing customer information. Failures before changes can reopen the previous release; after migrations, dependency changes or asset publication begins, maintenance stays on for review.

Fix the cause and push reviewed corrections, then:

```bash
python "$HOME/apps/smartliving/deployer/deploy.py" --resume
```

Only after explicitly verifying old code is compatible with the current database and installed dependencies:

```bash
python "$HOME/apps/smartliving/deployer/deploy.py" --rollback --schema-compatible
```

Rollback backs up the current data, restores previous public static files and switches code; it does not restore SQL, delete uploads or undo package installation. If schema compatibility is uncertain, restore the matching snapshot into an isolated recovery app/database and reconcile newer enquiries before switching traffic.

Backups use the configured public MEDIA_ROOT, not stale shared/media. Keep backup archives and settings outside public_html, copy encrypted backups off-host and rehearse restoration. No old releases or backups are automatically deleted; monitor disk/inodes, including retained hashes and no-change candidate checkouts. Never delete the active or rollback release. Runtime WAF, CDN, cPanel restart behaviour and asset permissions still require actual hosting checks.
