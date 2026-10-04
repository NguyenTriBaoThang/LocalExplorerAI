# Data model

This schema incorporates the team's PostgreSQL 15+ / PostGIS ERD. PostgreSQL uses
`text[]` for tag/reason lists, `jsonb` for documents, `bigint` for VND amounts,
and `geometry(Point, 4326)` plus a GiST index for POI locations. SQLite is used
only by the API test suite and maps the same collection fields to JSON.

```mermaid
erDiagram
    PROVIDERS ||--o{ EXPERIENCES : offers
    POIS ||--o{ EXPERIENCES : hosts
    EXPERIENCES ||--o{ EXPERIENCE_SLOTS : schedules
    EXPERIENCES ||--o{ INTENT_SIMILARITIES : similarity_a
    EXPERIENCES ||--o{ INTENT_SIMILARITIES : similarity_b
    EVIDENCE }o--o| POIS : "target_type=poi"
    EVIDENCE }o--o| EXPERIENCES : "target_type=experience"
    EVIDENCE }o--o| EXPERIENCE_SLOTS : "target_type=slot"
    ITINERARIES ||--o{ ITINERARY_STOPS : contains
    ITINERARIES ||--o{ ITINERARY_VERSIONS : snapshots
    ITINERARIES ||--o{ DECISION_LOGS : explains
    ITINERARIES ||--o{ FEEDBACKS : receives
    EXPERIENCE_SLOTS ||--o{ ITINERARY_STOPS : uses
    POIS ||--o{ ITINERARY_STOPS : location
    EXPERIENCES ||--o{ ITINERARY_STOPS : activity
    EVENTS o|--o{ DECISION_LOGS : triggers
    USERS ||--o{ BOOKINGS : requests
    PROVIDERS ||--o{ BOOKINGS : serves
    ITINERARIES o|--o{ BOOKINGS : context
    ITINERARY_STOPS o|--o{ BOOKINGS : requested_stop
    EXPERIENCE_SLOTS ||--o{ BOOKINGS : reserves
    EXPERIENCES ||--o{ BOOKINGS : books
    BOOKINGS ||--o{ BOOKING_EVENTS : history
    BOOKINGS ||--o{ PAYMENT_TRANSACTIONS : payments

    USERS {
      varchar id PK
      varchar role
      varchar provider_id FK
    }

    PROVIDERS {
      uuid id PK
      varchar name
      varchar slug UK
      varchar contact_phone
      varchar address
      boolean is_active
      varchar verification_status
      varchar portal_access_key
    }
    POIS {
      varchar id PK
      varchar name
      varchar district
      varchar address
      double latitude
      double longitude
      geometry geom
      varchar category
      text source_attribution
      int data_revision
      uuid submitted_by_provider_id FK
      boolean is_in_pilot_polygon
      jsonb image_urls
    }
    EXPERIENCES {
      varchar id PK
      varchar poi_id FK
      uuid provider_id FK
      varchar title
      text description
      text_array intent_tags
      boolean is_hands_on
      boolean is_indoor
      integer duration_min
      bigint price_vnd
      varchar verification_status
      int data_revision
    }
    EXPERIENCE_SLOTS {
      uuid id PK
      varchar experience_id FK
      timestamptz start_at
      timestamptz end_at
      integer capacity_total
      integer available_reported
      varchar status
      integer version
      timestamptz confirmed_at
      timestamptz expires_at
    }
    INTENT_SIMILARITIES {
      varchar experience_a_id PK,FK
      varchar experience_b_id PK,FK
      float semantic_similarity
      float tag_overlap_score
      float final_score
      boolean is_human_reviewed
    }
    ITINERARIES {
      uuid id PK
      varchar user_session_id
      varchar city
      date planned_date
      timestamptz start_time
      timestamptz return_deadline
      integer group_size
      bigint budget_vnd
      varchar travel_mode
      jsonb target_intents
      varchar status
      integer current_version
    }
    ITINERARY_STOPS {
      uuid id PK
      uuid itinerary_id FK
      integer stop_order
      uuid slot_id FK
      varchar poi_id FK
      varchar experience_id FK
      timestamptz arrival_at
      timestamptz departure_at
      integer wait_duration_min
      integer activity_duration_min
      bigint cost_vnd
      boolean is_locked
      varchar status
    }
    ITINERARY_VERSIONS {
      uuid id PK
      uuid itinerary_id FK
      integer version_number
      jsonb stops_snapshot
      bigint total_cost_vnd
      integer total_travel_time_s
      float preserved_intents_ratio
    }
    EVENTS {
      uuid id PK
      varchar event_type
      varchar target_type
      varchar target_id
      timestamptz valid_until
      varchar status
      jsonb metadata
    }
    DECISION_LOGS {
      uuid id PK
      uuid itinerary_id FK
      uuid trigger_event_id FK
      integer base_version
      integer new_version
      text_array preserved_intents
      text_array lost_intents
      text_array reason_codes
      jsonb comparative_metrics
      text explanation_vi
    }
    FEEDBACKS {
      uuid id PK
      uuid itinerary_id FK
      integer rating
      text comment
      timestamptz created_at
    }
    EVIDENCE {
      uuid id PK
      varchar source_uri
      varchar source_type
      varchar source_label
      varchar license
      varchar target_type
      varchar target_id
      int target_revision
      jsonb fields_covered
      timestamptz observed_at
      timestamptz verified_at
      timestamptz expires_at
    }
    BOOKINGS {
      varchar id PK
      varchar user_id FK
      varchar provider_id FK
      varchar itinerary_id FK
      varchar itinerary_stop_id FK
      varchar experience_id FK
      varchar slot_id FK
      integer quantity
      bigint amount_vnd
      varchar currency
      varchar status
      timestamptz hold_expires_at
      timestamptz provider_confirmed_at
      timestamptz confirmed_at
    }
    PAYMENT_TRANSACTIONS {
      varchar id PK
      varchar booking_id FK
      varchar provider
      varchar provider_reference
      varchar idempotency_key
      bigint amount_vnd
      varchar currency
      varchar status
      varchar checkout_url
    }
    BOOKING_EVENTS {
      varchar id PK
      varchar booking_id FK
      varchar actor_user_id FK
      varchar event_type
      varchar from_status
      varchar to_status
      jsonb details
      timestamptz created_at
    }
```

`intent_similarities` stores each pair once (`experience_a_id < experience_b_id`)
and constrains all three scores to `[0, 1]`. Slot status accepts the team's
`open | full | cancelled` values; legacy `available | unavailable | tentative`
values remain supported for existing API/demo data. `feedbacks` is intentionally
minimal because the team's ERD references it but does not define its columns.

The first project schema used `name`, `indoor`, `position`, `start_at`/`end_at`,
and other fields that current API clients depend on. These columns remain as
compatibility fields alongside the team's canonical `title`, `is_indoor`,
`stop_order`, `departure_at`, and other fields. The planner writes both forms.
Identifiers remain string-backed to preserve existing UUID values while also
accepting the human-readable POI/experience IDs in the team's design.

Migration `0002_team_database_architecture` adds the missing tables and columns,
backfills existing rows, upgrades VND columns to `bigint`, converts tag/reason
lists to PostgreSQL arrays, and converts POI geography to geometry. Migration
`0001_initial` is kept as a frozen baseline so future ORM changes cannot alter
the historical migration.

Migration `0005_sourced_catalog_evidence` attaches evidence to a POI, experience,
or slot with a typed target ID, target revision, field coverage, observation
time, source, and expiry. This is a deliberate polymorphic reference; the
service validates the target and provider ownership. Editing a POI or
experience increments its revision and makes evidence for the older version
ineligible. Migration `0006_provider_poi_ownership` adds the owner pointer for
provider-submitted POIs. See [sourced catalog workflow](sourced-catalog.md).

Migration `0007_booking_payments` adds temporary reservations (`bookings`), a
gateway transaction ledger (`payment_transactions`), and state/audit history
(`booking_events`). Provider acceptance is distinct from paid confirmation.
VNPay transaction references and payment state are stored in the ledger, while
the signed IPN—not the browser redirect—settles paid bookings. Refund execution
remains disabled and requires manual reconciliation. See [booking and payment
workflow](bookings-and-payments.md).

The PRD lists 32 HCMC POI names grouped into eight areas, but does not provide
their coordinates, addresses, source attribution, provider links, activities,
or schedule data. Therefore those names are not inserted as operational POI
rows with fabricated locations. The existing seed remains explicitly synthetic;
the supplied POI catalogue can be loaded once its source data is completed and
verified. The eight named areas are represented by `pois.district` rather than
a separate region table, matching the ERD.
