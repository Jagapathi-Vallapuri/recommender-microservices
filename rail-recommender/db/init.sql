-- Rail recommender Postgres schema (idempotent)

CREATE TABLE IF NOT EXISTS trains (
  train_number INTEGER PRIMARY KEY,
  train_name TEXT NOT NULL,
  station_name TEXT NOT NULL,
  departure TEXT NOT NULL,
  source TEXT NULL,
  destination TEXT NULL
);

CREATE TABLE IF NOT EXISTS train_interactions (
  id BIGSERIAL PRIMARY KEY,
  user_id TEXT NOT NULL,
  train_number INTEGER NOT NULL REFERENCES trains(train_number) ON DELETE CASCADE,
  interaction_type TEXT NOT NULL,
  ts TEXT NOT NULL,
  rating DOUBLE PRECISION NULL
);
