# POI source import and verification queue

The source workbook `data/raw/Sai_Gon_Places.xlsx` is registered in the database as an admin-only import batch. Its rows are stored in `place_import_candidates`, not `pois`; they do not appear in customer search or itinerary planning until independently enriched and verified.

To preview a future workbook import, run from `apps/api`:

```powershell
.\.venv\Scripts\python.exe -m scripts.import_place_candidates --dry-run
```

To stage it in the admin queue, omit `--dry-run`. Imports are idempotent by SHA-256. The script does not create POIs, experiences, prices, opening hours, or slots.

Review the batch in Admin → Imported POIs. Before creating operational catalog records, add evidence-backed addresses and unique geocodes, source URLs and observation dates, price basis, current opening hours, and hands-on/activity details as applicable. A `verified` flag in the spreadsheet is retained as source data but is not accepted as verification evidence.

The current workbook has 177 rows. The current dry-run finds a source URL, address text, opening hours, and price basis for each row, but the addresses are marked `reverse_geocoded_needs_POI_confirmation`, all listed prices are marked `source_file_value_unverified`, and all rows are marked `field_level_evidence_pending_not_publishable`. All 177 source `verified` flags are therefore unsubstantiated by the required field-level evidence. Two rows also use repeated coordinate pairs. No row was promoted to the live catalog.

The admin import queue also shows deterministic POI-label suggestions from the supplied `kind`, `tags`, `description`, and `outdoor` fields. Suggestions include a broad place type, supported intent/topic tags, and indoor/outdoor labeling. Hands-on is marked only when the source text explicitly describes visitor participation; otherwise it remains unknown at POI level. The labels are versioned as `poi-label-suggestions-v1`, are computed at read time, and do not alter the source workbook, promote a candidate, verify evidence, or create a human post-trip relevance grade.
