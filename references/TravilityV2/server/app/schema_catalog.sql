CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS users (
  id serial PRIMARY KEY,
  email text UNIQUE NOT NULL,
  password_hash text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS destinations (
  slug text PRIMARY KEY,
  name text NOT NULL,
  lat double precision NOT NULL,
  lon double precision NOT NULL
);
ALTER TABLE destinations ADD COLUMN IF NOT EXISTS hubs jsonb NOT NULL DEFAULT '{}';

CREATE TABLE IF NOT EXISTS places (
  id serial PRIMARY KEY,
  ext_id text UNIQUE NOT NULL,
  destination text NOT NULL REFERENCES destinations(slug),
  name text NOT NULL,
  kind text NOT NULL,
  lat double precision NOT NULL,
  lon double precision NOT NULL,
  price integer NOT NULL DEFAULT 0,
  open_hours jsonb NOT NULL DEFAULT '{}',
  outdoor boolean NOT NULL DEFAULT false,
  tags text[] NOT NULL DEFAULT '{}',
  description text NOT NULL DEFAULT '',
  photo_url text,
  embedding vector(768) NOT NULL
);
