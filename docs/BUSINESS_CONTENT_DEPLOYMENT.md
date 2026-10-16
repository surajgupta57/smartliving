# Solutions, services and project content

The supplied content adds five solutions, four services and three project
planning guides. It follows the existing catalogue categories and site-survey
service choices. It contains no invented customers, installation photographs,
project completions, prices, accreditations or guaranteed response times.
No stock or generated image is presented as a real installation.

All pages are editable in Admin > CMS > Content pages. Project planning guides
are a separate content type from project case studies and appear on /projects/.
Publish actual customer case studies only with verified details and permission.

## Production installation

1. Back up the production database using the production deployment guide.
2. Deploy the updated code, including apps/cms/business_content.py, the management
   command, CMS migration, views and templates. A database export alone does not
   install the new project-guide routing or template changes.
3. Activate the production virtual environment and select config.production as
   described in PRODUCTION_DEPLOYMENT_GUIDE.md. From the directory with manage.py:

   ```bash
   python manage.py migrate --noinput
   python manage.py seed_business_content --dry-run
   python manage.py seed_business_content
   python manage.py production_check
   ```

4. Restart the application using the host's normal release procedure. Check
   /solutions/, /services/ and /projects/, open each detail page, and follow the
   enquiry links. On an empty CMS the command creates 12 published pages.

The command runs in a transaction and matches pages by kind and slug. Re-running
it does not create duplicates, overwrite editor changes or republish drafts.
It does not change products, users, enquiries or existing unrelated CMS pages.
If it reports preserved pages, review those pages in Admin: the local version may
differ from an editor's version on production. No extra media upload is required
for this text-only starter content.

## Moving later edits from local Admin

After editing these pages locally, open Admin > CMS > Content pages > Export,
choose JSON and export the desired records. On production use the same Content
pages Import screen, review the preview, then confirm. These records match by
kind and slug, so an import can deliberately update an existing page. Back up and
review changes first; unlike the seed command, an import can overwrite live copy.

If you add card or hero images later, copy their files into the production media
storage with their relative paths preserved before importing the JSON. Keep
content exports private. The initial supplied pages have no media dependencies.
