# POI source import and verification queue

The source workbook `data/raw/Sai_Gon_Places.xlsx` is registered in the database as an admin-only import batch. Its rows are stored in `place_import_candidates`, not `pois`; they do not appear in customer search or itinerary planning until independently enriched and verified.

To preview a future workbook import, run from `apps/api`:

```powershell
.\.venv\Scripts\python.exe -m scripts.import_place_candidates --dry-run
```

To stage it in the admin queue, omit `--dry-run`. Imports are idempotent by SHA-256. The script does not create POIs, experiences, prices, opening hours, or slots.

Review the batch in Admin → Imported POIs. Before creating operational catalog records, add evidence-backed addresses and unique geocodes, source URLs and observation dates, price basis, current opening hours, and hands-on/activity details as applicable. A `verified` flag in the spreadsheet is retained as source data but is not accepted as verification evidence.

The current workbook has 177 rows. All are flagged as needing enrichment: the sheet lacks addresses and source URLs, has no opening hours or price basis, and reuses four coordinate pairs across the rows. Therefore no row was promoted to the live catalog.
