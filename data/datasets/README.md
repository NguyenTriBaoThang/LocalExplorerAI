# LocalExplorerAI catalog datasets

Copied from `D:\MyProject\MLAI_DEMO_T7\LocalExplorerAI-main\data`.

- `catalog.json`: portable catalog snapshot intended for database import (202 POIs and 202 experiences, plus related records). Import it with `python -m scripts.portable_catalog import /data/datasets/catalog.json` from the API container.
- `catalog_inventory.json`: table counts and snapshot metadata.
- `sai_gon_places.json`: 177-place Saigon catalog.
- `district1_osm_places.json`: 2,326 District 1 OSM entries.
- `district1_osm_places_with_local_photos.json`: the same OSM entries with local photo references.

The portable snapshot is reference/demo data. POIs and experiences retain simulated or unverified status; imported slots are tentative with zero availability. Do not use these records for real bookings until reviewed and verified. Original datasets remain in their existing `data/` locations.
