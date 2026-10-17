-- Bảng theo User: nằm ở shard user_id % N khi có SHARD_URLS, không thì chung database với schema_catalog.sql.
CREATE TABLE IF NOT EXISTS trips (
  id serial PRIMARY KEY,
  -- users nằm ở database chung nên không có khoá ngoại; user_id luôn lấy từ JWT đã kiểm (spec scale §9.1)
  user_id integer NOT NULL,
  spec jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE trips DROP CONSTRAINT IF EXISTS trips_user_id_fkey;  -- database tạo trước khi tách shard
ALTER TABLE trips ADD COLUMN IF NOT EXISTS user_messages text[] NOT NULL DEFAULT '{}';
-- change_trip đang chờ người dùng đồng ý ({changes, message, text}); gõ "oke" cũng lập lại được
ALTER TABLE trips ADD COLUMN IF NOT EXISTS pending_replan jsonb;

CREATE TABLE IF NOT EXISTS itineraries (
  id serial PRIMARY KEY,
  trip_id integer NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
  version integer NOT NULL,
  data jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (trip_id, version)
);

-- Disruption → Proposal; kiêm log feedback (đã hiện gì, chọn gì) cho ranker (spec revision-giu-muc-dich §5.1)
CREATE TABLE IF NOT EXISTS proposals (
  id serial PRIMARY KEY,
  trip_id integer NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
  base_version integer NOT NULL,
  disruption jsonb NOT NULL,
  options jsonb NOT NULL,
  no_feasible text[],
  chosen_index integer,
  applied_version integer,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS group_review_proposals (
  id serial PRIMARY KEY,
  trip_id integer NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
  source_version integer NOT NULL,
  base_version integer NOT NULL,
  feedback text NOT NULL,
  candidate jsonb NOT NULL,
  status text NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'applied', 'cancelled')),
  applied_version integer,
  created_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (trip_id, source_version) REFERENCES itineraries(trip_id, version),
  FOREIGN KEY (trip_id, base_version) REFERENCES itineraries(trip_id, version),
  FOREIGN KEY (trip_id, applied_version) REFERENCES itineraries(trip_id, version)
);
CREATE INDEX IF NOT EXISTS group_review_proposals_trip
  ON group_review_proposals(trip_id, id DESC);

-- Pinned Stop: thuộc Trip, không thuộc version; gán vào stop.pinned khi đọc (spec revision-day-du §2 D2)
ALTER TABLE trips ADD COLUMN IF NOT EXISTS pinned_place_ids integer[] NOT NULL DEFAULT '{}';

-- Lịch sử chat theo Trip để mở lại thấy hội thoại (#17); không lưu thinking/tool_call/clarify/error
CREATE TABLE IF NOT EXISTS messages (
  id serial PRIMARY KEY,
  trip_id integer NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
  role text NOT NULL CHECK (role IN ('user', 'ai')),
  text text NOT NULL,
  version integer,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS messages_trip ON messages(trip_id, id);
