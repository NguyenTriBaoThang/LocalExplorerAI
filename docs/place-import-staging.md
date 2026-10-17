# POI source import and verification queue

The source workbook `data/raw/Sai_Gon_Places.xlsx` is registered in the database as an admin-only import batch. Its rows are stored in `place_import_candidates`, not `pois`; they do not appear in customer search or itinerary planning until independently enriched and verified.

To preview a future workbook import, run from `apps/api`:

```powershell
.\.venv\Scripts\python.exe -m scripts.import_place_candidates --dry-run
```

To stage it in the admin queue, omit `--dry-run`. Imports are idempotent by SHA-256. The script does not create POIs, experiences, prices, opening hours, or slots.

## Dataset intake: `Sai_Gon_Places_v2.xlsx`

The workbook supplied on 2026-10-15 is preserved at
`data/raw/Sai_Gon_Places_v2.xlsx`. Preview the 15 Quận 1 POI candidates with:

```powershell
.\.venv\Scripts\python.exe -m scripts.import_place_candidates --source ..\..\data\raw\Sai_Gon_Places_v2.xlsx --worksheet Verified_District1 --dry-run
```

Omit `--dry-run` to register those POI rows in the admin-only queue. The
`Sai_Gon` sheet can be staged separately by selecting `--worksheet Sai_Gon`.
The workbook hash is scoped to the selected worksheet, so two sheets from the
same workbook remain separate import batches.

The workbook's own labels are source claims, not reviewed evidence. In its
`Sai_Gon` sheet, `verification_status` says 167 `unverified` and 10 `verified`,
while the Boolean `verified` column is true on 20 rows. The separate
`Verified_District1` sheet has 15 rows marked `verified`; they still enter the
queue as candidates. The source records use `full_address`, which the importer
maps to the application's `address` field. The imported `fields_covered`, URL,
license/terms, photo credit, observation time, and expiry remain visible for
review and are never auto-approved. Each source submission must select only
the POI fields that its URL actually supports. Multiple sources can be
submitted for one pending candidate; moderators approve each source, and the
POI remains unpublished until current approved evidence covers every required
field. The 15 POI rows cite 8 distinct HTTPS URLs. Their field coverage, source
terms, and per-image reuse rights still need row-by-row review.

| Worksheet | Rows | Intake findings |
| --- | ---: | --- |
| `Sai_Gon` | 177 | Address, observation time, expiry, and photo credit are each unknown/missing on 167 rows; all 177 lack a photo URL. Only 10 rows have HTTPS source URLs. |
| `Verified_District1` | 15 | Address, coordinates, dates, and photo URL/credit are populated. The `fields_covered` entries are still claims, and the workbook has no separate per-image license field. |
| `Experiences_Verified` | 15 | URL, dates, duration, price, and basis are populated, but the sheet has no `fields_covered` column, so it does not establish which experience fields each URL supports. |

These are workbook contents, not independent verification of the linked pages.

The `Experiences_Verified` sheet is not imported into the POI queue or turned
into experiences. It has 15 rows marked `verified`, but no `fields_covered`
column. Submit an experience separately after its linked POI is approved and
its activity, duration, price, and pricing basis have suitable evidence. Slots
must be created by an authenticated provider with a current capacity report.
The supplied workbook contains no slots. Any slots or behavior rows described
as synthetic in the accompanying inventory are for demo/ETL checks only and
must not be loaded as real availability or user behavior.

The bundled `dataset_v1/scripts/import_dataset.py` is not the project importer:
it hard-codes paths from another machine, writes directly to a separate
SQLite database, creates a synthetic provider, and inserts source claims as
approved evidence. Do not run it against the application database.

Review the batch in Admin → Imported POIs. A POI needs current evidence for its name, address, latitude, longitude, and category. Price, pricing basis, intent, hands-on status, and duration belong to a separately submitted experience. Start/end times and capacity belong to provider-confirmed slots. A `verified` flag in a spreadsheet is retained as source data but is not accepted as verification evidence.

The original workbook at `data/raw/Sai_Gon_Places.xlsx` has 177 rows. Its earlier dry-run found address text and source-file values but marked the addresses `reverse_geocoded_needs_POI_confirmation`, prices `source_file_value_unverified`, and field-level evidence pending. It is an older source batch, separate from the v2 workbook audit above. No row from either workbook is promoted to the live catalog by import.

The admin import queue also shows deterministic POI-label suggestions from the supplied `kind`, `tags`, `description`, and `outdoor` fields. Suggestions include a broad place type, supported intent/topic tags, and indoor/outdoor labeling. Hands-on is marked only when the source text explicitly describes visitor participation; otherwise it remains unknown at POI level. The labels are versioned as `poi-label-suggestions-v2`, are computed at read time, and do not alter the source workbook, promote a candidate, verify evidence, or create a human post-trip relevance grade.

Dataset validation reports only structural checks. It does not establish that a
live URL supports the listed fields, that a source or photo license permits
reuse, or that an experience has current prices or capacity. Review those
claims directly before approving evidence.

`apps/api/scripts/seed_saigon_places.py` is disabled. It previously filled missing facts and generated POI/experience/slot evidence under fabricated URLs; running that loader would create records that look operational without provider confirmation. Use the candidate import and review flow above. Do not publish a POI before its required fields have current approved evidence. Do not create availability until a provider has confirmed the slot and capacity.
