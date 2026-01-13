-- Airline recommender Postgres schema (idempotent)

CREATE TABLE IF NOT EXISTS flights (
  flight_number TEXT PRIMARY KEY,
  airline TEXT NOT NULL,
  source TEXT NOT NULL,
  destination TEXT NOT NULL,
  departure TEXT NOT NULL,
  arrival TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_interactions (
  id BIGSERIAL PRIMARY KEY,
  user_id TEXT NOT NULL,
  flight_number TEXT NOT NULL REFERENCES flights(flight_number) ON DELETE CASCADE,
  interaction_type TEXT NOT NULL,
  ts TEXT NOT NULL,
  rating DOUBLE PRECISION NULL
);
