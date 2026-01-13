from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
import random
import string
import time
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import psycopg2
from psycopg2.extras import RealDictCursor, execute_values

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


DATABASE_URL = os.getenv("DATABASE_URL")


def _require_database_url() -> str:
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set")
    return DATABASE_URL


def _connect():
    # For long-running services, autocommit avoids idle-in-transaction sessions.
    conn = psycopg2.connect(_require_database_url())
    conn.autocommit = True
    return conn


def _random_flight_number() -> str:
    prefix = "".join(random.choices(string.ascii_uppercase, k=2))
    suffix = "".join(random.choices(string.digits, k=4))
    return f"{prefix}{suffix}"


def _random_timestamp_iso(days_back: int = 365) -> str:
    now = datetime.now(timezone.utc)
    delta = timedelta(seconds=random.randint(0, days_back * 24 * 3600))
    return (now - delta).replace(microsecond=0).isoformat()


def _seed_if_empty():
    airlines = [
        "AirNova",
        "SkyJet",
        "BlueCloud",
        "AeroPulse",
        "SunWing",
        "PolarAir",
        "QuantumFly",
        "MetroAir",
    ]

    airports = [
        "SFO",
        "LAX",
        "JFK",
        "ORD",
        "DFW",
        "SEA",
        "MIA",
        "DEN",
        "BOS",
        "ATL",
    ]

    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS flights (
                    flight_number TEXT PRIMARY KEY,
                    airline TEXT NOT NULL,
                    source TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    departure TEXT NOT NULL,
                    arrival TEXT NOT NULL
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS user_interactions (
                    id BIGSERIAL PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    flight_number TEXT NOT NULL REFERENCES flights(flight_number) ON DELETE CASCADE,
                    interaction_type TEXT NOT NULL,
                    ts TEXT NOT NULL,
                    rating DOUBLE PRECISION NULL
                );
                """
            )

            cur.execute("SELECT COUNT(*) AS cnt FROM flights;")
            flights_count = cur.fetchone()[0]
            if flights_count == 0:
                flight_numbers = []
                seen = set()
                while len(flight_numbers) < 500:
                    fn = _random_flight_number()
                    if fn in seen:
                        continue
                    seen.add(fn)
                    flight_numbers.append(fn)

                now = datetime.now(timezone.utc)

                flight_rows = []
                for fn in flight_numbers:
                    source = random.choice(airports)
                    destination = random.choice([a for a in airports if a != source])

                    depart_dt = now + timedelta(minutes=random.randint(0, 60 * 24 * 7))
                    depart_dt = depart_dt.replace(second=0, microsecond=0)

                    duration_minutes = random.randint(60, 6 * 60)
                    arrive_dt = (depart_dt + timedelta(minutes=duration_minutes)).replace(second=0, microsecond=0)

                    flight_rows.append(
                        (
                            fn,
                            random.choice(airlines),
                            source,
                            destination,
                            depart_dt.isoformat(),
                            arrive_dt.isoformat(),
                        )
                    )
                execute_values(
                    cur,
                    "INSERT INTO flights (flight_number, airline, source, destination, departure, arrival) VALUES %s",
                    flight_rows,
                )

            cur.execute("SELECT COUNT(*) AS cnt FROM user_interactions;")
            interactions_count = cur.fetchone()[0]
            if interactions_count == 0:
                cur.execute("SELECT flight_number, source, destination FROM flights;")
                flights_meta = list(cur.fetchall())

                segments = []
                for _ in range(6):
                    src = random.choice(airports)
                    dst = random.choice([a for a in airports if a != src])
                    segments.append((src, dst))

                user_ids = [str(uuid4()) for _ in range(300)]
                user_segment = {uid: random.choice(segments) for uid in user_ids}

                seg_to_flights: dict[tuple[str, str], list[str]] = {seg: [] for seg in segments}
                all_flight_numbers = []
                for fn, src, dst in flights_meta:
                    all_flight_numbers.append(fn)
                    seg = (src, dst)
                    if seg in seg_to_flights:
                        seg_to_flights[seg].append(fn)

                interaction_types = ["View", "Search", "Book"]
                rows = []
                for _ in range(5000):
                    user_id = random.choice(user_ids)
                    pref_seg = user_segment[user_id]

                    interaction_type = random.choices(
                        interaction_types,
                        weights=[0.55, 0.25, 0.20],
                        k=1,
                    )[0]

                    candidate_flights = seg_to_flights.get(pref_seg) or all_flight_numbers
                    if random.random() < 0.75 and candidate_flights:
                        flight_number = random.choice(candidate_flights)
                        matches_preference = True
                    else:
                        flight_number = random.choice(all_flight_numbers)
                        matches_preference = False

                    rating = None
                    if interaction_type == "Book":
                        if matches_preference:
                            rating = round(random.uniform(3.6, 5.0), 1)
                        else:
                            rating = round(random.uniform(1.0, 4.2), 1)

                    rows.append(
                        (
                            user_id,
                            flight_number,
                            interaction_type,
                            _random_timestamp_iso(days_back=540),
                            rating,
                        )
                    )

                execute_values(
                    cur,
                    """
                    INSERT INTO user_interactions (user_id, flight_number, interaction_type, ts, rating)
                    VALUES %s
                    """,
                    rows,
                )


@app.on_event("startup")
def startup_event():
    last_exc = None
    for _ in range(15):
        try:
            with _connect() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1;")
            _seed_if_empty()
            return
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            time.sleep(2)
    raise RuntimeError(f"Postgres did not respond in time: {last_exc}")


@app.get("/flights")
async def get_flights(limit: int = 100):
    with _connect() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    flight_number AS "flightNumber",
                    airline,
                    source,
                    destination,
                    departure,
                    arrival
                FROM flights
                ORDER BY flight_number
                LIMIT %s
                """,
                (limit,),
            )
            return list(cur.fetchall())


@app.get("/users")
async def get_users(limit: int = 100):
    with _connect() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    user_id AS "userId",
                    flight_number AS "flightNumber",
                    interaction_type AS "interactionType",
                    ts AS "timestamp",
                    rating
                FROM user_interactions
                ORDER BY id
                LIMIT %s
                """,
                (limit,),
            )
            return list(cur.fetchall())


@app.get("/health")
def health():
    return {"status": "healthy"}
