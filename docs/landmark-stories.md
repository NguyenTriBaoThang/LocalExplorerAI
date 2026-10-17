# 3D landmark discovery and editorial timeline

Click a model or its accessible information button on `/map-3d` to open the discovery card. It contains Overview, History, Architecture and Visit sections. Escape or the close button collapses it. The card becomes a bottom sheet on small screens and keeps the map visible. Historical dates do not change the model into an unsupported historical reconstruction.

## Data and review

`landmark_stories` stores separate draft and published JSON documents keyed by known model ID. A monotonically increasing revision detects stale edits. PostgreSQL row locks serialize edits, submit, publication and unpublication. All writes require `admin:content` under the existing authentication, MFA and CSRF policies; actions are recorded in the audit log. Anonymous reads return only the published document, never the draft or editor identity.

Portal → Nội dung → Câu chuyện địa danh 3D:

1. Choose a landmark and enter sources with HTTPS URLs and access dates.
2. Edit the overview, images with attribution, dated/period-based events, architecture details and visiting information. Select sources for each claim. Events are ordered by starting year, preserving editorial order for equal years.
3. Save draft, submit for review, open preview, then approve and publish. The same `admin:content` role can edit and approve; this is not a mandatory two-person approval process.
4. Editing a published story preserves the previous public version. Unpublish hides the public version and retains the draft. Revision conflicts require reloading; unsaved content is not silently overwritten.

Source links and dates record provenance; they are not an automated fact-check. Editorial `sourced` status is independent of the operational POI/experience verification system. Unsourced visiting information is explicitly labelled. Sourced hours and prices require a check date. No booking availability is inferred from historical content. Calendar precision is represented by an editorial period label and numeric ordering year, so a century/range need not invent an exact date.

## Installation

From `apps/api`:

```sh
python -m alembic upgrade head
python -m scripts.seed_landmark_stories --publish
```

Migration `0019_landmark_stories` only adds the new table. Back up the database before migration. The seed inserts missing stories only and never overwrites editorial changes; omit `--publish` to install drafts for review. It does not modify users, bookings, experiences or existing POI records. Docker's existing API image copies `app/` and `scripts/`, including the sample JSON files.

Four concise sourced samples are included in `apps/api/app/data/landmark_stories/`: Notre Dame Cathedral (5 milestones), Independence Palace (4), Municipal Theatre (5), and Ben Thanh Market (1). Fewer events are intentional when no additional sources have been verified. Models without published stories show an honest empty state and still expose directions. Images for the palace and theatre reuse attributed Commons assets in the existing manifest; other images are omitted rather than copied without known rights.

## Sources reviewed

- Cathedral: https://www.chinhtoasaigon.org/gioi-thieu and https://tgpsaigon.net/bai-viet/vuong-cung-thanh-duong-duc-ba-sai-gon-37259
- Palace: https://dinhdoclap.gov.vn/lich-su-dinh-doc-lap/
- Theatre: https://csdl.vietnamtourism.gov.vn/dest/?item=381
- Market: https://vietnamtourism.vn/en/index.php/tourism/items/511

The seed records the editorial source-access date. There is no fabricated visit duration, ticket price or current opening schedule. New locations can be authored in Portal without rebuilding the web.

## Validation

`tests/test_landmark_stories.py` checks permission boundaries, draft isolation, publication workflow, stale revisions, invalid URLs/references/date ranges, audit logging and idempotent samples. `test_rbac.py` includes the new public endpoint in the explicit reviewed inventory. Frontends must both pass TypeScript/Vite builds. UI smoke checks should include desktop/mobile, collapse and Escape, source links, timeline expansion, model switching, retry/empty state, and admin preview/publish.

Voice narration and historical 3D reconstruction are separate follow-ups; neither is required to read and manage the sourced timeline.
