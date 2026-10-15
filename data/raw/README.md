# Raw source data

Files in this folder are source material or candidates for review. Their presence does not make them operational catalog records or valid training data.

## Current contents

- district1_osm_places.json: OpenStreetMap candidates whose representative points fall inside a historical District 1 pilot polygon. Coverage may be incomplete; records do not confirm that a venue is still open or provide current prices, opening hours, or slots.
- district1_osm_photos_manifest.json and district1_osm_places_with_local_photos.json: image-source metadata and candidate associations. Each image must be checked against its source page, license, and credit requirements; not every place has a matching image.
- Sai_Gon_Places.xlsx: the project workbook. Its 177 rows still need field-level source evidence before approval.
- hcmc_flood_reports_2002_2026.csv: a conversion of historical reports from DataSuds. It does not provide verified dry periods or the road-edge labels needed for road-flood prediction.
- flood_training.csv: not presumed to be a valid training dataset. Check schema and provenance; do not synthesize no-flood labels or observation timestamps.

## Handling and licensing

Keep source files unchanged for reproducibility. Record hashes and collection dates in a manifest or report, and follow the provider's terms. OpenStreetMap requires attribution and applicable ODbL obligations. Wikimedia images have file-specific licenses.

See the [ML data guide](../../docs/ml-training-and-data.md) for flood data and [place import guide](../../docs/place-import-staging.md) for POI intake.
