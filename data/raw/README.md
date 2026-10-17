# Raw source data

Files here are sources or candidates for review. They are not automatically operational data.

## Current contents

- district1_osm_places.json: OSM candidates collected within the historical District 1 pilot polygon. This is not a complete list of every place and does not verify that a venue is open or confirm its current price, hours, or slots.
- district1_osm_photos_manifest.json and district1_osm_places_with_local_photos.json: image metadata and candidate image associations. Use an image only when its source page, license, and credit can be checked for that specific file; not every place has a matching image.
- Sai_Gon_Places.xlsx: a project-provided workbook with 177 rows that still need source review and field-level evidence before approval.
- Sai_Gon_Places_v2.xlsx: a newer source workbook preserved for review. Its `Verified_District1` sheet is staged as POI candidates only; its `Experiences_Verified` sheet is not auto-imported, and it contains no slot data. The workbook's verification labels and field coverage are unreviewed claims.
- hcmc_flood_reports_2002_2026.csv: a converted historical report dataset from DataSuds. It has no verified dry windows or road-edge labels required for flood prediction.
- flood_training.csv: must not be assumed to be a valid training set. Check its schema and provenance; do not synthesize no-flood labels or observation times.

## Handling and licensing

Keep original source files for reproducibility. Record hashes and collection dates in a manifest or report. Follow provider terms. OSM-derived data requires attribution and applicable ODbL obligations. Wikimedia images have licenses specific to each file.

For flood reports, see the [dataset notes](../../docs/ml-training-and-data.md). For POI intake, see [place import staging](../../docs/place-import-staging.md).
