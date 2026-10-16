# Smart Living Technologies

> **Current hosting instructions (16 October 2026):** follow [the working cPanel configuration](docs/CPANEL_WORKING_CONFIGURATION.md). The owner reported the site working after replacing the recursive Passenger loader and using real public static/media directories. The older symlink layout below is not the layout to reapply on this account. The updated deployer supports these public roots; follow [the automation setup](docs/DEPLOYMENT_AUTOMATION.md) before its first run.

A standalone Django lead-generation catalogue for smart-home automation, CCTV, security, networking, installations, and AMC enquiries. It is intended to be served at `smartliving.seas-india.com`, but it is not coupled to the SEAS application or its branding.

## Run locally

1. Create and activate a virtual environment, then install `requirements.txt`.
2. Copy `.env.example` into your deployment environment and set a unique `DJANGO_SECRET_KEY`.
3. Run `python manage.py migrate`.
4. Run `python manage.py createsuperuser`.
5. Run `python manage.py runserver` and open `http://127.0.0.1:8000/`.

## First operator workflow

1. Open `/admin/` and create **Site settings**. Set the real business name, contacts, WhatsApp number, social/SEO details, and confirm `https://smartliving.seas-india.com` as the public URL.
2. Create a category and optional brand. Or run `python manage.py seed_smartliving_categories` to create the 21 editable categories supplied for this website.
3. Create a product with a primary category, then add specifications, features, gallery images, documents, and a featured image using the product admin inlines.
4. Mark the product active and published. Visit `/products/`, open it, add it to the quote list, and send a product enquiry.

## Production hand-off

- Point the `smartliving` DNS record at the hosting account and configure that host in `DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS`.
- Set `DJANGO_DEBUG=False`, `DJANGO_SECURE_SSL_REDIRECT=True`, a private secret, persistent media storage, and run `collectstatic --noinput`.
- Use a production database where available. SQLite is only the local default.
- Product image uploads are limited to 8 MB each; files, documents, content, product status, page sections, and contact identity are administered through Django Admin.

## Sales workspace

Open `/workspace/` after signing in at `/admin/login/`. The workspace has an enquiry pipeline, owner assignment, priority, scheduled follow-ups, activity history and quotation management. Search enquiries by name, phone or email; filter by stage, assigned-to-me or overdue follow-ups.

Run `python manage.py seed_sales_roles`. In Admin → Users, mark approved operators as **staff** and assign **Sales operator** or **Sales viewer**. No accounts or passwords are created by this command. Superusers can access the workspace directly.

From an enquiry, choose **Create quotation**, enter products/installation/service lines and applicable tax rates, then save a draft. Drafts can be edited. **Mark as sent** records manual delivery; it does not email the customer. Staff can then record acceptance or decline. Sent quotations cannot be edited; create a new quotation to revise an offer. Use **Print / save PDF** for a customer copy. This is a quotation workflow, not accounting or tax invoicing.

Production rollout still requires real catalogue/content, confirmed business contact details, configured deployment secrets, HTTPS, backups, and staff access setup. Payment collection, automatic messaging, inventory/accounting integration and installation scheduling are not implemented.

## Portable 500-product manufacturer catalogue

See `catalogue_seed/manufacturers/README.md` for local/live installation and import behavior. The complete offline bundle is `catalogue_seed/manufacturers/manifest.json` plus its referenced `assets/` directory. Run `python manage.py seed_manufacturer_catalogue --dry-run` before importing with `--publish`. Existing products and staff media are preserved on reruns. The `SL-...` identifier is an internal SKU; manufacturer model and source provenance are separate fields.


## Live search and MySQL deployment

Install `pip install -r requirements-mysql.txt` for MySQL hosting. Set server environment variables
`DJANGO_DB_ENGINE=mysql`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST` (default localhost),
and `DB_PORT` (default 3306). Keep credentials outside source control. Use a supported MySQL 8 database.
SQLite remains the local default. Changing engines does not transfer existing data: back up and transfer
catalogue/CMS data separately before switching production traffic.

After deployment run:
```
python manage.py migrate
python manage.py rebuild_product_search
python manage.py collectstatic --noinput
```
Search uses an indexed token table with AND matching and word/model prefixes (not arbitrary middle-of-word matches).
Suggestions require two characters and return at most eight products without counts, images, or specifications.
Filter pages load only 12/24/48 products. Product and brand saves refresh the index automatically.
Run `rebuild_product_search` after bulk_create, QuerySet.update, raw fixture loads, or external database imports.
The first rebuild is required for existing products. It is idempotent and processes products in chunks.
Large catalogue capacity depends on host CPU, memory, database limits, filter selectivity and deep pagination;
validate with realistic data and concurrent traffic on the actual hosting plan before claiming lakh-scale latency.


For local MySQL setup and transfer, run `.\.venv\Scripts\python.exe scripts/setup_local_mysql.py`.
It prompts for the existing MySQL administrator password locally, creates `smartliving` and
`smartliving_app` restricted to that database, generates a password into ignored `.env`, migrates,
transfers SQLite data and rebuilds search. It refuses existing database/user/.env names.
The administrator password is not saved. Keep `.env` private and exclude it from distributed archives.
If migration/import fails, credentials remain in `.env` for recovery; SQLite is unchanged.


## Site-survey requests and follow-up

Customers use `/site-survey/` (linked from the footer and contact/quote pages) to provide property type,
site address, service requirements and preferred date/time in IST. Requests require contact consent
and a future preferred time; no booking, price promise or notification is made automatically.
Staff use `/workspace/enquiries/?surveys=1`, open the enquiry, then Manage visit.
Viewing visits requires `leads.view_consultation`; editing also requires `leads.change_consultation`
and `leads.view_enquiry`. Confirm the time and any charges with the customer before scheduling.
Existing enquiry owner, priority, next follow-up date, activity history and quotation workflow remain
available on the same enquiry. Assign staff permissions through Django Admin.


## Catalogue performance benchmark

Run `.\.venv\Scripts\python.exe scripts/benchmark_catalogue.py` for an isolated MySQL
benchmark with 100,000 synthetic products, token indexes and one image record per product.
The command prompts for the local database administrator account, creates a uniquely named test
database, exercises suggestions, filters, sorting and deep pagination, then removes that test database.
It never seeds synthetic products into the configured business database. The generated report is
`var/catalogue-benchmark.json`; use `--report` to preserve multiple runs. `--workers` controls
concurrent requests (default 4), and `--requests` controls the concurrent sample count (default 40).

When MySQL is unavailable, `--sqlite --report var/catalogue-benchmark-sqlite.json` provides a
development measurement in an isolated SQLite file. SQLite results cannot validate MySQL capacity.
These are local Django timings: they exclude network latency, browser work and image delivery,
and do not reproduce the CPU/memory limits of a shared-hosting plan.

The configured local MySQL instance uses port 3307, normally managed by Windows service `MySQL80`.
Check connectivity first: an instance may also be running manually even when the service says Stopped.
If port 3307 is unavailable, open PowerShell as Administrator and run `Start-Service MySQL80`, then
restart Django if needed.

## Complete production deployment guide

Use [docs/PRODUCTION_DEPLOYMENT_GUIDE.md](docs/PRODUCTION_DEPLOYMENT_GUIDE.md) for first-time cPanel/Passenger + MySQL setup, DNS/HTTPS, private environment configuration, data/media transfer, catalogue seeding, staff permissions, launch checks, routine updates, backups and rollback.

See `PERFORMANCE_REPORT.md` for the 100,000-product MySQL comparison and validation limits.


## Guided product finder

`/product-finder/` is linked from the homepage, catalogue and quote list. It collects property type,
main priority, room/camera counts, coverage, camera family preference and indicative budget.
It shows up to eight published products from existing published category families; it does not
claim verified site suitability, availability, system compatibility or a priced bill of materials.
Verified planning profiles now refine coverage and camera technology. Camera count checks verified companion capacity; exact INR prices are checked against the budget ceiling. Room counts remain intake for a site assessment.

Choosing a quote or survey explicitly saves the validated brief in the visitor's session and pre-fills
an editable enquiry form. The existing quote shortlist stays intact. Contact details and consent
are still required before any enquiry is created. The brief clears after successful quote/survey submission.

## Verified compatibility guidance

Open **Admin → Catalogue → Products → select a product → Product compatibility rows**
or **Admin → Catalogue → Product compatibility pairings** to manage directional pairings.
Choose a companion and role (recorder, PoE/power, controller/hub, accessory or other).
Record the exact supported configuration and limitations in Requirements: protocols,
PoE standard and budget, channel/capacity limits, firmware, hub and regional requirements
as applicable. Add a manufacturer/test evidence URL and the date checked before marking
the pairing verified. Only active, verified, dated pairings with two public products appear.
No compatibility claims are seeded automatically. Verification is staff-managed; revisit
pairings when firmware, hardware revisions or manufacturer information changes.

Product pages show **Works with** and an **Add both products to quote** button.
This adds one of each missing product, preserves existing quantities and refuses the whole
addition if the 12-product quote limit would be exceeded. Relationships are directional;
add a separate reverse relationship if appropriate. A pair does not certify a whole system
or determine quantities. Existing general compatibility text remains available.

Apply migrations before deploying this feature. Compatibility records are managed in Admin
and are not included in the existing product CSV transfer; preserve them with database backups.

The curated starter command adds T1C → A3 and T2C → A3 manufacturer-documented
sensor/gateway pairings, reviewed on 15 October 2026. They are not hardware-tested.
Run `python manage.py seed_verified_compatibility --dry-run`, then
`python manage.py seed_verified_compatibility` on the intended database.
All three public products must exist with their original manufacturer source URLs.
The command preserves existing pairings, including staff edits and deactivations.


## Requirement-based planning checks

Edit **Admin → Catalogue → Products → select a product → Product planning profile**.
Add one profile per product, selecting its role and verified environment/camera technology.
Enter recorder channels for recorders, usable PoE ports/output budget for switches, and
maximum PoE demand for cameras only when supported by manufacturer documentation.
Record the evidence URL and date, then enable Verified. Unknown values remain unknown;
never derive outdoor suitability from IP camera terminology or operating temperature alone.

The finder excludes known verified conflicts before choosing up to eight results and
prioritises products with verified profiles. Unverified, undated and future-dated profiles
are not used to assert suitability. Both indoor/outdoor coverage requires a profile allowing
both; mixed indoor-only/outdoor-only systems still require team planning.

For CCTV, listed camera cost uses the planned camera count (one if unspecified). Other
project types use one unit for the product-cost check. Only exact INR prices are compared
against a budget ceiling; starting prices and unknown prices require quotation. Lower
budget-band bounds are not minimum product-price requirements. Costs do not establish
a complete project budget and do not include unspecified equipment or services.

Only existing verified compatibility pairings produce companion options. Known recorder
channel or PoE port/power shortages exclude the pairing; incomplete capacities are labelled
for confirmation. PoE standards, per-port limits, storage, bandwidth, site headroom and
compatibility between different companions still need review. No automatic bill of materials
or installation quantities are created. Quote and survey handoffs preserve the existing shortlist.

Two initial profiles record Wi-Fi camera technology for Tapo C100 and C200 from their
TP-Link India product pages, reviewed 15 October 2026. Environment and power fields are
left unknown. Other profiles must be populated by staff. All current products are quote-priced,
so real budget matching becomes effective after exact prices are entered.

Run `python manage.py migrate` through catalogue migration 0010 before using this feature.
Planning profiles are not part of the existing product CSV transfer; preserve them through
database backups or recreate them in Admin on the destination database.


## Production release (cPanel / Passenger)

Use [docs/PRODUCTION_LAUNCH.md](docs/PRODUCTION_LAUNCH.md). The strict `config.production` profile requires private credentials, exact hosts, MySQL and HTTPS; local `.env` settings remain for development. `scripts/init_production_env.py` generates an exclusive private template without displaying its secret. Install `requirements-production.txt`, migrate, relocate legacy document files, collect manifest static assets, and run `manage.py production_check --settings=config.production`.

Product documents are stored in private `var/private_documents` (or DJANGO_PRIVATE_DOCUMENT_ROOT) and served as checked attachments through `/documents/...`. They are included separately in `backup_site` backups. Transfer these private files separately from public media.

Build the allowlisted source ZIP with `python scripts/build_release.py`. Add `--include-catalogue` only when the offline seed assets are needed. Credentials, live records/media, private files and generated outputs are excluded. The old catalogue seed ZIP is not the production release.

## Public image optimisation

See [IMAGE_OPTIMIZATION.md](docs/IMAGE_OPTIMIZATION.md) for lossless WebP display copies, responsive product images and the server command. Original uploads remain unchanged.
