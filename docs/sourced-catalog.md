# Sourced Catalog Data

## Purpose and Status

The operational catalog is distinguished from demo data by approval status,
evidence tied to the exact data revision, and a valid expiry. The API does not
crawl automatically, verify website content, or create real data by itself.
Venues submit sources/evidence; administrators review POIs, activities, and
related evidence. Slot confirmations come from an authenticated venue account
and always include a confirmation time and expiry.

Seed POIs/experiences and the 10 POIs returned by the web fallback have
`data_mode: simulated`. The web interface labels them as simulated; they do not
count as verified POIs/experiences and must not be approved into the operational
catalog merely because they exist in a mock. The operational API does not return
a record as `verified` if evidence is missing, belongs to a different revision,
or has expired. Expired real slots are excluded from search and planning;
simulated slots remain explicitly labeled as simulated.

## Stored Data

- POI: name, address, coordinates, type/category; each record has a `data_revision` and the account of the venue that created it.
- Experience: description/activity type, `intent_tags`, `is_hands_on`, duration, price, and pricing basis; also has a `data_revision`.
- Slot: start/end time, capacity, provider-reported availability, status, `confirmed_at`, `expires_at`, and `version`.
- Evidence: source URI, source type/name, license/terms, fields supported by the source, `observed_at`, `expires_at`, submitter, reviewer/status, `target_type`, `target_id`, `target_revision`, and notes.

Evidence uses `target_type` values `poi`, `experience`, or `slot`. Because one
table supports several record types, the target is a polymorphic relationship;
the API validates the target and ownership instead of pretending there is one
shared foreign key. A POI or experience is approved only when approved,
unexpired evidence for the matching revision covers all required fields: a POI
requires `name`, `address`, `latitude`, `longitude`, and `category`; an
experience requires `title`, `description`, `primary_intent`, `intent_tags`,
`is_hands_on`, `duration_min`, `price_vnd`, and `price_basis`; a slot requires
`start_at`, `end_at`, `capacity_total`, `available_reported`, and `status`. An
edit increments the revision, so old sources cannot verify the new values. A
slot created/updated by a venue is stored as a direct authenticated
confirmation; an update increments the version and makes earlier slot evidence
no longer match. Expiry thresholds are not inferred: the submitter chooses the
expiry, the administrator can see it, and the API does not use evidence after
that time.

## Workflow

1. A venue creates a POI or experience with `pending` status, including source
   URL/type, observation time, and expiry, and marks exactly which fields the
   source supports. For address/coordinates, mark the POI fields only if the
   source/check actually supports them.
2. An administrator reviews each piece of evidence first. Expired evidence,
   evidence without an observation time, a missing target, or a changed target
   revision is rejected.
3. The administrator approves a POI after all required fields have current
   evidence. An experience is approved only after its evidence is complete and
   its linked POI is approved.
4. A venue creates a slot with initial capacity, the server records its
   confirmation time, and the submitted confirmation expiry must be no later
   than the slot's start time. Updating a slot increments its version, stores a
   new confirmation, and requires an explicit expiry to reopen it.
5. Users see status/source labels in the catalog and on each itinerary stop.
   When reloaded, an older stop is marked `verified`, `stale`, `simulated`, or
   `unverified`; POI/experience/slot sources are returned separately, with the
   slot's confirmation time and expiry. If POI or experience sources expire, or
   a slot is no longer fresh, the data is not presented as currently verified.

## API

- `POST /api/provider/pois` and `PATCH /api/provider/pois/{id}` — create/edit a
  venue POI; each edit returns it to `pending` and increments its revision.
- `POST /api/provider/experiences` and `PATCH /api/provider/experiences/{id}` —
  create/edit an experience; each edit increments its revision and returns it
  to `pending`.
- `POST /api/provider/evidence` — submit a source for a POI or experience owned
  by the venue. Timestamps must include a timezone, the URI must use HTTP(S),
  the observation time cannot be in the future, and the expiry must follow the
  observation time and remain valid.
- `POST /api/provider/experiences/{id}/slots` — create a slot with required
  `expires_at`. The venue is treated as the direct source; the API records
  internal evidence and `confirmed_at`.
- `PATCH /api/provider/slots/{id}` — optimistic update by version; reopening a
  slot requires a valid `expires_at` no later than its start time.
- `GET /api/admin/moderation?status=pending` and
  `PATCH /api/admin/moderation/{evidence|poi|experience}/{id}` — review queue
  and approval. The `CATALOG_EVIDENCE_INCOMPLETE` error response identifies
  fields that are still missing.
- `GET /api/pois`, `GET /api/experiences`, `GET /api/experiences/{id}` — return
  `data_mode`, status, and `source_evidence` for matching records; sources
  include URI, field scope, observation time, and expiry.
- `POST /api/itineraries/plan`, `GET /api/itineraries/{id}` — each stop returns
  POI/experience/slot provenance, freshness status, slot confirmation/expiry
  timestamps, and source IDs in `explanation.evidence_refs`. Mock routing status
  is reported separately and does not label a sourced catalog as simulated.

## Pilot Targets

An earlier draft proposed 20–30 POIs, 10–15 experiences, 30–50 slots, and
outreach to 3–5 venues. These are planned targets, not collected data or limits
enforced by the software. The team must reconfirm the numbers before finalizing
the plan; the API does not create records to meet them.

## Remaining Limitations

- No external information has been crawled or collected for this workflow yet;
  real sources must be supplied/authorized by venues or be public sources with
  a suitable license.
- An administrator currently reviews content and sources; there is no OCR,
  crawler, or automatic verification. Record field-survey procedures in the
  source/notes.
- Existing mock POIs cannot replace a sourced catalog; verified POIs, addresses,
  and coordinates must be entered through the provider/admin form before adding
  real experiences.
- There is no booking/payment here; slot confirmation only reports availability
  at `confirmed_at` and remains valid until `expires_at`.
