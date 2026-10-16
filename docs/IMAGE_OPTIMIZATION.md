# Public image optimisation

Smart Living can serve pre-generated responsive WebP copies of uploaded images while keeping the originals and database filenames unchanged. This follows the purpose of the SEAS optimiser without replacing originals or reusing its application/database.

WebP encoding here is lossless for the generated pixels. Smaller copies are resized with Lanczos; resizing necessarily reduces pixel detail, so this is not a claim that a thumbnail equals the original full-resolution image. The original remains available for large displays. Transparency and embedded colour profiles are retained for supported RGB images. Animated/unsupported images are left unchanged. Only outputs smaller in bytes than the original are kept.

## Server commands

Deploy the code normally first. Activate the Smart Living virtualenv in cPanel Terminal and use the same private production environment as the deployer:

```bash
export DJANGO_ENV_FILE="$HOME/apps/smartliving/shared/.env"
cd "$HOME/apps/smartliving/current"
python manage.py optimize_public_images --dry-run --limit 30 --settings=config.production
```

Review the report. A dry run performs image processing to measure sizes but writes nothing. Then generate copies for all database-referenced public images:

```bash
python manage.py optimize_public_images --settings=config.production
```

Large libraries take time; run the first pass during a quiet period and allow it to finish. A --limit 30 write run can be used as a small initial trial. Later full runs skip unchanged prepared images. Do not run multiple copies concurrently. Missing/corrupt files are reported with record IDs; originals remain the page fallback, and the command exits nonzero if errors occurred.

## What changes on the website

- Product cards use responsive srcset/sizes so the browser can select a suitable image for its screen and pixel density.
- The main product image and gallery thumbnails use prepared copies; switching gallery images also updates srcset to avoid showing the previous selection.
- Uploaded CMS card, hero and homepage images also use prepared copies.
- Existing lazy loading remains on cards/thumbnails; the main product image is not lazy loaded.
- Originals remain in the responsive choices when a smaller generated file cannot provide the necessary resolution. Without prepared copies, the original URL is used immediately.

Image encoding never runs during public page requests. Generating variants is an offline maintenance operation. This does not alter private PDFs, other documents, database data, static hero assets or videos. Bundled static images are already deployed through collectstatic.

## New Admin uploads

Uploads continue to work immediately using their original images. Run the command again after new uploads, or add an hourly cPanel cron after the initial pass succeeds. Use the exact interpreter printed by `python -c "import sys; print(sys.executable)"` in the activated app environment. Example template (replace ACTUAL_VENV with that interpreter):

```bash
DJANGO_ENV_FILE=/home/a7bc3w2x98u9/apps/smartliving/shared/.env /ACTUAL_VENV/bin/python /home/a7bc3w2x98u9/apps/smartliving/current/manage.py optimize_public_images --settings=config.production >> /home/a7bc3w2x98u9/apps/smartliving/logs/image-optimization.log 2>&1
```

Do not enable cron while the initial full job is still running. Inspect logs and rotate them. No cron job or server optimisation has been installed by the local code change.

## Storage, backups and validation

Copies are stored below the configured MEDIA_ROOT/optimized/images/v1, which on this account is public_html/smartliving/media/optimized/images/v1. Existing media/.htaccess protections apply. Generated files are ordinary public assets, not symlinks. They remain excluded from Git through media/.

This reduces browser downloads; **it does not reduce the disk size of originals or private-document backups**. It adds a small regenerable cache to media, currently included in backup_site media snapshots. It does not implement a new backup policy. Old variants are not deleted automatically when originals change; review storage growth separately rather than deleting active files during deployment.

After generation, inspect an actual product card in browser Network tools: the selected currentSrc should use /media/optimized/images/v1/ when a suitable smaller copy exists, return 200 with image/webp, and have a lower transferred size. Check mobile/high-density screens, transparent backgrounds and gallery selection. File-size savings and local tests do not prove production load-time or Core Web Vitals improvement; measure those on the live hostname.

## Standalone in-place server compression

Upload scripts/compress_uploaded_media.py to current/scripts/ and activate the app virtualenv. This standalone script needs only Pillow, not Django or the responsive-image deployment. Defaults target $HOME/public_html/smartliving/media and private $HOME/apps/smartliving/backups/media-optimization.

```bash
python "$HOME/apps/smartliving/current/scripts/compress_uploaded_media.py" --limit 30
python "$HOME/apps/smartliving/current/scripts/compress_uploaded_media.py" --apply
```

The first command is a read-only preview. The second checks every supported public image and replaces each file immediately after successful compression, pixel/orientation verification and a verified original backup. Same filename, format, dimensions and URL are retained; no database changes. It never resizes or uses lossy encoding. Animated images and unusual colour modes are skipped. JPEG requires host-provided jpegtran; without it, JPEGs are skipped rather than recompressed lossily. Existing compact WebP files may not shrink at all.

Only changed originals are backed up, not the entire media library. Backups are private timestamped originals/ trees with manifest.jsonl containing relative filenames and before/after hashes. Preserve those backups until restored files have been tested. Restore a reviewed original by copying the matching originals/relative/path back to active MEDIA_ROOT/relative/path, during a quiet upload period. Do not copy the whole backup directory into public media or blindly overwrite newer uploads.

Run one write job at a time during quiet traffic; a Linux lock prevents another script instance. Files changed by an upload while being processed are not overwritten. Interrupted runs may leave an unused backup/temp file; inspect those privately before cleanup. Skipped PDFs, videos and private documents require separate workflows. The generated responsive-image cache is excluded. After in-place source changes, rerun optimize_public_images to generate current responsive copies; older variants remain until a separate reviewed cleanup.

After replacing bytes at unchanged URLs, use a hard refresh and, if necessary, purge only affected image URLs from a configured CDN. Monitor actual response size and image appearance. This script cannot guarantee savings for files that are already efficiently compressed.
