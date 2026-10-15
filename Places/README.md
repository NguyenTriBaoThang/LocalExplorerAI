# Places data

This folder contains the project's original places workbook, Sai_Gon_Places.xlsx. It is a source spreadsheet for review and import; it is not, by itself, the live operational catalog.

The workbook covers places and activities in Ho Chi Minh City, with an emphasis on District 1, District 3, and Cho Lon. Values in the workbook—including any verified flag—must be supported by current, field-level evidence before they are approved for operational use.

## Import and review

The API importer stores rows in an admin-only staging queue. It does not automatically create live POIs, experiences, prices, opening hours, or slots.

From apps/api, preview the import and then stage it for review:

~~~powershell
python -m scripts.import_place_candidates --dry-run
python -m scripts.import_place_candidates
~~~

Review the batch in Admin → Imported POIs. Resolve duplicate or ambiguous coordinates, attach source evidence for relevant fields, and have an administrator review it before promoting a record. See [place import and verification](../docs/place-import-staging.md).

The current audit of the 177-row workbook marks its rows as not publishable under the field-level evidence checks. In particular, the address/coordinate relationship and listed prices still need source confirmation. A source workbook flag is not a substitute for that evidence.

## Related resources

- Staged workbook copy: data/raw/Sai_Gon_Places.xlsx
- Raw-data notes: data/raw/README.md
- Place and evidence scripts: scripts/README.md
- User-facing pages: /places and /places/:id
- Catalog API: apps/api/app/api/routes/catalog.py
