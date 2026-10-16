# Local to live data transfer

Open `/admin/` and select a model. The **Import** and **Export** buttons support JSON, Excel (.xlsx), and CSV. Prefer **JSON** for lossless transfers of long specifications, nested homepage configuration, dates, and customer phone numbers. Export can use the current filtered list; import first shows a review screen and requires confirmation before saving.

Superusers can transfer data. Other staff need **Core → Can import business data / Can export business data**, plus the relevant model permissions. Enquiry exports also require **Leads → Can export enquiries**. These permissions allow bulk changes, so grant them deliberately.

## Import order

1. Brands.
2. Categories: root categories first, then children whose parent slugs already exist.
3. Products.
4. Product specifications, features, images, and documents.
5. Content pages, homepage sections, FAQs, and site settings can be transferred independently.
6. Enquiries, followed by enquiry items and consultations. Create the required staff usernames on live before importing assigned enquiries.

Products match by stable slug, SKU, and manufacturer source key. Brand and category references use slugs; enquiry references use transfer UUIDs. Database row IDs are excluded from imports, so different local/live IDs do not misattach records. Repeated imports update matching records rather than create another copy. Do not edit the transfer identifiers in exported files. Duplicate/missing identifiers and unknown related records reject the import.

An admin import **updates values supplied in the file**, unlike the manufacturer seed command, which preserves all existing products. Back up the destination and review changes before confirming. CSV/Excel export escapes formula-like strings for spreadsheet safety; JSON is preferable when importing the data again.

## Images, galleries, and PDFs

Data exports store media filenames, not the binary files. Select records and choose **Export selected records’ media files (.zip)** from the Actions menu. Selecting Products includes their featured images, gallery images, and documents. Brands, categories, CMS pages, homepage sections, site settings, gallery images, and documents also offer their own media action.

Copy the ZIP contents to the destination `MEDIA_ROOT`, preserving the relative folders, **before** importing the data. If production uses object storage, upload the same relative object keys there. Imports reject missing media and absolute/unsafe filenames. Media ZIP export reads existing files and does not change records. For a full transfer, export each related model listed above as well as its media.

Quotation headers, quotation lines, and lead activity history have **Export only**. Their changes remain controlled through the staff sales workspace; administrative bulk imports cannot bypass quotation transitions or rewrite audit history. Those exports are reporting archives, not a complete database restore. Use a full database backup for disaster recovery or migration of existing quotation history. Users/passwords are also excluded from this transfer workflow.

## Bundled 500-product catalogue

Extract `smartliving-catalogue-500.zip` into a matching application checkout, deploy the included application changes and install requirements, then run:

```shell
python manage.py migrate
python manage.py seed_manufacturer_catalogue --dry-run
python manage.py seed_manufacturer_catalogue --publish
python manage.py collectstatic --noinput
```

The seed command imports the included verified image/PDF assets into configured media storage; it needs no manufacturer network access. It preserves matching existing products and staff edits. Without `--publish`, new products remain drafts. The ZIP contains catalogue assets and application changes, not your database, customer data, passwords, or environment secrets.

Production must persist the `import_export` storage configured in `STORAGES` outside public media. The default uses `var/private_imports`; multiple application workers/hosts need shared private storage so preview and confirmation can access the same upload. Remove abandoned preview uploads periodically using the storage backend's retention policy. Restart the application after deployment.
