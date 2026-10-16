# Smart Living catalogue performance verification

Date: 15 October 2026. Local MySQL, 100,000 synthetic products, 1,000,000 indexed search tokens and one image database record per product. Synthetic data was created only in temporary test databases.

## Changes verified

- Added composite indexes for public product ordering by featured status, name, and price in both directions.
- Restricted catalogue-card queries to the fields and primary image they display.
- Replaced duplicate-producing category joins with indexed category membership checks.
- Kept the first search-term lookup indexed and correlated subsequent terms to candidate products, reducing work for common multiword queries.
- Changed search-index rebuilding to bounded keyset batches of 500 products.

## Timings

Serial values are medians of five local in-process Django requests per workload. Maxima and query counts are retained in the JSON reports.

| Workload | Before (ms) | After (ms) |
|---|---:|---:|
| Broad live suggestions | 277.08 | 4.34 |
| Model-prefix suggestions | 3.38 | 3.38 |
| Multiword suggestions | 1166.09 | 55.36 |
| Catalogue first page | 1466.93 | 35.02 |
| Category and brand filters | 602.00 | 56.31 |
| Broad search result page | 1735.48 | 160.67 |
| Catalogue page 2000 | 2067.25 | 193.23 |
| Price sorting (low to high) | 1450.26 | 55.59 |

The mixed concurrent run used four clients and 40 total requests across the eight workloads.

| Concurrent metric | Before | After |
|---|---:|---:|
| Median latency (ms) | 680.1 | 91.15 |
| 95th-percentile latency (ms) | 2530.75 | 293.3 |
| Requests per second | 4.09 | 29.52 |

## Validation and limits

- 39 catalogue and lead workflow tests passed on isolated MySQL databases.
- Django checks and migration drift checks passed.
- The business catalogue retained its 500 products.
- Temporary benchmark databases were removed after each run.
- These are short local measurements, not a sustained production stress test or shared-hosting guarantee. They exclude browser rendering, network latency and image file delivery. Real descriptions, product distributions, concurrent writes and hosting CPU/memory limits may change results.
- Test the same workloads on the intended hosting plan before making a customer-facing performance commitment.

## Reproduce

Run `.\.venv\Scripts\python.exe scripts/benchmark_catalogue.py` and enter the local MySQL administrator credentials at the prompts. The script uses a uniquely named temporary database and removes it when finished. It refuses an existing temporary database name.

Raw measurements: [before](var/catalogue-benchmark-mysql-before.json), [after](var/catalogue-benchmark-mysql-after.json).
