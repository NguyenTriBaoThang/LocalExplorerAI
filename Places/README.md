# Local Explorer AI — Places directory

The Places/ directory stores the original field-survey workbook for the tourism, culture, food, and arts-workshop place catalog in Ho Chi Minh City.

---

## Workbook: Sai_Gon_Places.xlsx

| Property | Details |
|---|---|
| **File** | Places/Sai_Gon_Places.xlsx |
| **Purpose** | Original field-survey data for cultural and heritage places, notable restaurants, and craft workshops, focused on District 1, District 3, and Cho Lon |
| **Format** | Microsoft Excel (.xlsx) — source data before processing into JSON |

### Main fields

| Field | Description |
|---|---|
| ext_id | Extended place identifier |
| name | Place name (Vietnamese names may include diacritics) |
| kind | Category: heritage, culture, food, workshop, nature, or relaxation |
| lat, lon | GPS coordinates |
| price_vnd | Ticket price or reference cost in VND |
| open_hours | Weekly opening hours |
| outdoor | Outdoor (true) or indoor (false) |
| tags | Keywords used for search and intent matching |
| description | Description of history, architecture, and experience value |
| photo_url | Field/place image URL |
| verified | Source verification flag from the workbook |
| source | Referenced data source |

---

## Import and approval workflow

Under the fail-closed policy, this workbook must not be loaded directly into the operational database. It goes through staging and review.

### Step 1: Import into staging

~~~powershell
cd apps/api

# Preview the records that would be imported:
python -m scripts.import_place_candidates --dry-run

# Import candidates into place_import_candidates:
python -m scripts.import_place_candidates
~~~

### Step 2: Review and approve

- An administrator reviews Admin → Staging Places or the /api/admin/staging-places/* API.
- The system flags possible duplicates using fuzzy string similarity (threshold ≥ 0.88).
- Review GPS coordinate validity and opening-hours evidence.
- Approve records individually or in bulk only after the required evidence has been reviewed; approved POIs are promoted to the main POI table.

### Step 3: Enrich and validate

~~~powershell
# Collect District 1 place candidates and eligible source images:
python scripts/crawl_district1_places.py
python scripts/download_district1_photos.py
python scripts/attach_district1_photos_to_catalog.py

# Check data integrity:
python scripts/deep_check_excel.py
python scripts/check_places_detail.py
~~~

A crawler result or a workbook verified flag is not, by itself, field-level evidence. Every source and image must comply with its license and attribution terms. The current 177-row workbook audit still marks the rows as not publishable until their evidence is reviewed.

---

## Related resources

| Resource | Location |
|---|---|
| Staged JSON catalog source | data/raw/ |
| User-facing place pages | /places and /places/:id |
| 3D Landmark Viewer | /map-3d — GLB landmark models |
| Data processing scripts | scripts/ |
| Catalog API | apps/api/app/api/routes/catalog.py — /api/pois and /api/experiences |
