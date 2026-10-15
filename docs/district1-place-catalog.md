# Collecting and Viewing the District 1 Pilot Place Catalog

`scripts/crawl_district1_places.py` queries named POIs on OpenStreetMap through Overpass, then retains objects whose representative coordinates fall inside the project's historic District 1 pilot polygon. This is a source-data collection tool; it does not claim to include “every real-world venue.”

## Run the Collection

Run from the repository root:

```powershell
& ".\apps\api\.venv\Scripts\python.exe" scripts/crawl_district1_places.py --output data/raw/district1_osm_places.json
```

By default, the tool looks for images explicitly linked through `wikimedia_commons`, a Commons-style `image` value, or Wikidata P18. Each image record is stored with its file-page URL, license name, license URL, and attribution. If no suitable image with license metadata is found, the record has `photo_status=not_found`; the application does not substitute an illustrative image. Skip image lookup for a faster run with `--skip-photos`.

Import the JSON into the admin review queue (this does not publish POIs automatically):

```powershell
Set-Location apps/api
& ".\.venv\Scripts\python.exe" scripts/import_place_candidates.py --source ../../data/raw/district1_osm_places.json --worksheet OSM --dry-run
& ".\.venv\Scripts\python.exe" scripts/import_place_candidates.py --source ../../data/raw/district1_osm_places.json --worksheet OSM
```

An administrator checks each source and address, adds evidence if needed, and submits it for approval. Crawling does not create prices, experiences, opening hours, slots, capacity, or verification status. Once a POI is added to the catalog, `/places` lists it; select an item to view `/places/{id}`, which shows attributed images, address, opening hours/website/contact/fees when present in the source, coordinates, raw OSM data, sources, observation time, and experiences linked to the POI.

If upgrading the schema from an older version:

```powershell
Set-Location apps/api
& ".\.venv\Scripts\alembic.exe" upgrade head
```

## Sources, Limitations, and Licenses

- Places/tags/coordinates: [OpenStreetMap](https://www.openstreetmap.org/copyright), ODbL-1.0 data; the interface must retain the attribution “© OpenStreetMap contributors.”
- Images: Wikimedia Commons API. Each file may have a different license; the application stores and displays the license/attribution from that file's metadata and does not assume all images share one license.
- Data depends on OSM and Wikidata coverage and update frequency. The polygon is the historic District 1 pilot boundary configured in the repository, not a current administrative boundary. Way/relation objects are filtered by their Overpass center coordinates; their geometry is not clipped precisely to the polygon.
- “All places” can only truthfully mean all records matching the source query at crawl time; it does not guarantee that every real-world shop/venue is recorded by the community map.
- Images without a source link or license are not added to the displayed gallery. Fields missing from the source remain blank/unavailable; they are not inferred.
- An OSM listing is not direct confirmation from a venue. Booking, prices, hours/slots, and capacity still require separate verification with the operator.
