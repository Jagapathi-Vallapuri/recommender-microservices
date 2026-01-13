from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import os
import random
import time
from datetime import datetime, timedelta

import psycopg2
from psycopg2.extras import RealDictCursor, execute_values

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "*"],
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
    conn = psycopg2.connect(_require_database_url())
    conn.autocommit = True
    return conn


class TrainData(BaseModel):
    train_number: str
    train_name: str
    station_name: str
    departure: str
    source: Optional[str]
    destination: Optional[str]


def _seed_if_empty():
    city_tokens = [
        "ALP",
        "BRV",
        "CRS",
        "DLT",
        "ECHO",
        "FST",
        "GLD",
        "HBR",
        "IVY",
        "JDE",
    ]

    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS trains (
                    train_number INTEGER PRIMARY KEY,
                    train_name TEXT NOT NULL,
                    station_name TEXT NOT NULL,
                    departure TEXT NOT NULL,
                    source TEXT NULL,
                    destination TEXT NULL
                );
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS train_interactions (
                    id BIGSERIAL PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    train_number INTEGER NOT NULL REFERENCES trains(train_number) ON DELETE CASCADE,
                    interaction_type TEXT NOT NULL,
                    ts TEXT NOT NULL,
                    rating DOUBLE PRECISION NULL
                );
                """
            )
            cur.execute("SELECT COUNT(*) FROM trains;")
            count = cur.fetchone()[0]
            if count != 0:
                return

            rows = []
            used_numbers = set()
            for i in range(500):
                while True:
                    train_number = random.randint(10000, 99999)
                    if train_number not in used_numbers:
                        used_numbers.add(train_number)
                        break

                src = random.choice(city_tokens)
                dst = random.choice([c for c in city_tokens if c != src])
                station_name = f"Station-{random.randint(1, 999)}"
                train_name = f"Express-{i + 1}"

                depart_dt = datetime.now() + timedelta(minutes=random.randint(0, 60 * 24 * 7))
                departure = depart_dt.replace(second=0, microsecond=0).isoformat(timespec="minutes")

                rows.append((train_number, train_name, station_name, departure, src, dst))

            execute_values(
                cur,
                """
                INSERT INTO trains (train_number, train_name, station_name, departure, source, destination)
                VALUES %s
                """,
                rows,
            )

            # Seed interactions if empty.
            cur.execute("SELECT COUNT(*) FROM train_interactions;")
            interactions_count = cur.fetchone()[0]
            if interactions_count == 0:
                segments = []
                for _ in range(8):
                    src = random.choice(city_tokens)
                    dst = random.choice([c for c in city_tokens if c != src])
                    segments.append((src, dst))

                user_ids = [str(random.randint(10**9, 10**10 - 1)) for _ in range(400)]
                user_segment = {uid: random.choice(segments) for uid in user_ids}

                cur.execute("SELECT train_number, source, destination FROM trains;")
                trains_meta = list(cur.fetchall())

                seg_to_trains: dict[tuple[str, str], list[int]] = {seg: [] for seg in segments}
                all_train_numbers: list[int] = []
                for tn, src, dst in trains_meta:
                    all_train_numbers.append(tn)
                    seg = (src, dst)
                    if seg in seg_to_trains:
                        seg_to_trains[seg].append(tn)

                interaction_types = ["View", "Search", "Book"]

                def random_timestamp_iso(days_back: int = 365) -> str:
                    now = datetime.now()
                    delta = timedelta(seconds=random.randint(0, days_back * 24 * 3600))
                    return (now - delta).replace(microsecond=0).isoformat(timespec="seconds")

                interaction_rows = []
                for _ in range(6000):
                    user_id = random.choice(user_ids)
                    pref_seg = user_segment[user_id]

                    interaction_type = random.choices(
                        interaction_types,
                        weights=[0.55, 0.25, 0.20],
                        k=1,
                    )[0]

                    candidate_trains = seg_to_trains.get(pref_seg) or all_train_numbers
                    if random.random() < 0.75 and candidate_trains:
                        train_number = random.choice(candidate_trains)
                        matches_preference = True
                    else:
                        train_number = random.choice(all_train_numbers)
                        matches_preference = False

                    rating = None
                    if interaction_type == "Book":
                        if matches_preference:
                            rating = round(random.uniform(3.6, 5.0), 1)
                        else:
                            rating = round(random.uniform(1.0, 4.2), 1)

                    interaction_rows.append(
                        (
                            user_id,
                            train_number,
                            interaction_type,
                            random_timestamp_iso(days_back=540),
                            rating,
                        )
                    )

                execute_values(
                    cur,
                    """
                    INSERT INTO train_interactions (user_id, train_number, interaction_type, ts, rating)
                    VALUES %s
                    """,
                    interaction_rows,
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


@app.get("/trains")
async def get_trains(limit: int = 100):
    with _connect() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT train_number, train_name, source, destination, station_name, departure
                FROM trains
                ORDER BY train_number
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
                    train_number AS "trainNumber",
                    interaction_type AS "interactionType",
                    ts AS "timestamp",
                    rating
                FROM train_interactions
                ORDER BY id
                LIMIT %s
                """,
                (limit,),
            )
            return list(cur.fetchall())


@app.post("/trains")
async def create_train(train: TrainData):
    try:
        train_number_int = int(train.train_number)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid train number format")

    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO trains (train_number, train_name, station_name, departure, source, destination)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (train_number) DO UPDATE SET
                    train_name = EXCLUDED.train_name,
                    station_name = EXCLUDED.station_name,
                    departure = EXCLUDED.departure,
                    source = EXCLUDED.source,
                    destination = EXCLUDED.destination
                """,
                (
                    train_number_int,
                    train.train_name,
                    train.station_name,
                    train.departure,
                    train.source,
                    train.destination,
                ),
            )
    return {"id": str(train_number_int)}


@app.get("/trains/{train_number}")
async def get_train(train_number: str):
    try:
        train_number_int = int(train_number)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid train number format")

    with _connect() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT train_number, train_name, source, destination, station_name, departure
                FROM trains
                WHERE train_number = %s
                """,
                (train_number_int,),
            )
            row = cur.fetchone()
            if row:
                return row

    raise HTTPException(status_code=404, detail="Train not found")


@app.get("/trains/source/{source}")
async def get_trains_by_source(source: str):
    with _connect() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT train_number, train_name, source, destination, station_name, departure
                FROM trains
                WHERE LOWER(source) = LOWER(%s)
                ORDER BY train_number
                """,
                (source,),
            )
            return list(cur.fetchall())


@app.get("/trains/route/{source}/{destination}")
async def get_trains_by_route(source: str, destination: str):
    with _connect() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT train_number, train_name, source, destination, station_name, departure
                FROM trains
                WHERE LOWER(source) = LOWER(%s) AND LOWER(destination) = LOWER(%s)
                ORDER BY train_number
                """,
                (source, destination),
            )
            rows = list(cur.fetchall())
            if rows:
                return rows

    raise HTTPException(status_code=404, detail="No trains found for this route")


@app.get("/health")
async def health():
    return {"status": "healthy"}
