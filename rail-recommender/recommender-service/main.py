from fastapi import FastAPI, HTTPException
import pandas as pd
import requests
import os
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
import time
from typing import Optional

from surprise import Dataset, Reader, SVD

load_dotenv()

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_SERVICE_URL = os.getenv("DATA_SERVICE_URL")

train_name_map = {}
train_route_map = {}
train_mean_rating = {}
booked_users = set()
algo = None
all_train_ids = []

@app.on_event("startup")
def load_and_prepare_data():
    global train_name_map, train_route_map, train_mean_rating, booked_users, algo, all_train_ids

    for _ in range(10):
        try:
            trains = requests.get(f"{DATA_SERVICE_URL}/trains", params={"limit": 5000}).json()
            users = requests.get(f"{DATA_SERVICE_URL}/users", params={"limit": 20000}).json()
            break
        except Exception as e:
            print(f"Waiting for data-service... {e}")
            time.sleep(3)
    else:
        raise RuntimeError("data-service did not respond in time")

    train_name_map = {str(t.get("train_number")): t.get("train_name", "Unknown") for t in trains if t.get("train_number") is not None}
    train_route_map = {
        str(t.get("train_number")): {
            "train_name": t.get("train_name", "Unknown"),
            "source": t.get("source"),
            "destination": t.get("destination"),
            "station_name": t.get("station_name"),
            "departure": t.get("departure"),
        }
        for t in trains
        if t.get("train_number") is not None
    }
    all_train_ids = list(train_route_map.keys())

    bookings = [
        u
        for u in users
        if u.get("interactionType") == "Book"
        and u.get("trainNumber") is not None
        and u.get("userId")
        and u.get("rating") not in (None, "", "NaN")
    ]

    df = pd.DataFrame(bookings)
    df = df.dropna(subset=["userId", "trainNumber", "rating"])
    df["rating"] = pd.to_numeric(df["rating"], errors="coerce")
    df = df.dropna(subset=["rating"])

    if df.empty:
        algo = None
        train_mean_rating = {}
        booked_users.clear()
        print("No booking data available; rail model not trained.")
        return

    train_mean_rating = df.groupby("trainNumber")["rating"].mean().to_dict()

    reader = Reader(rating_scale=(1, 5))
    data = Dataset.load_from_df(df[["userId", "trainNumber", "rating"]], reader)
    trainset = data.build_full_trainset()

    algo = SVD()
    algo.fit(trainset)

    booked_users.update(df["userId"])
    print("Rail recommendation model trained (SVD).")

def _format_train_details(train_number: str) -> dict:
    meta = train_route_map.get(train_number) or {}
    return {
        "id": train_number,
        "name": _format_train_name(train_number),
        "mode": "rail",
        "source": meta.get("source"),
        "destination": meta.get("destination"),
        "departure": meta.get("departure"),
        "arrival": None,
        "meta": {
            "stationName": meta.get("station_name"),
        },
    }


def _format_train_name(train_number: str) -> str:
    meta = train_route_map.get(train_number) or {}
    name = meta.get("train_name") or train_name_map.get(train_number, "Unknown")
    src = meta.get("source")
    dst = meta.get("destination")
    if src and dst:
        return f"{name} {src}→{dst}"
    return str(name)

@app.get("/recommend/{user_id}")
def recommend(user_id: str, top_n: int = 10):
    """User-based recommendations (collaborative filtering).

    Mirrors airline-style behavior: user_id -> ranked train IDs.
    """
    global booked_users, algo, all_train_ids

    if not user_id.strip():
        raise HTTPException(status_code=422, detail="User ID cannot be empty")

    if algo is None or not all_train_ids:
        raise HTTPException(status_code=503, detail="Model not trained")

    if user_id not in booked_users:
        top = all_train_ids[:top_n]
        return {
            "recommendations": [
                _format_train_details(tid)
                for tid in top
            ]
        }

    predictions = [algo.predict(user_id, tid) for tid in all_train_ids]
    predictions.sort(key=lambda x: x.est, reverse=True)
    ranked = [p.iid for p in predictions[:top_n]]
    return {
        "recommendations": [
            _format_train_details(tid)
            for tid in ranked
        ]
    }

    
@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.get("/recommend-route")
def recommend_route(source: str, destination: str, user_id: Optional[str] = None, top_n: int = 10):
    """Route-based recommendations using the same method as airline.

    If user_id is present and known, rank by SVD predicted rating.
    Otherwise rank by mean historical rating for this route.
    """
    global algo, booked_users, train_mean_rating

    src = (source or "").strip()
    dst = (destination or "").strip()
    if not src or not dst:
        raise HTTPException(status_code=422, detail="source and destination are required")

    route_trains = [
        tid
        for tid, meta in train_route_map.items()
        if (meta.get("source") or "").lower() == src.lower() and (meta.get("destination") or "").lower() == dst.lower()
    ]
    if not route_trains:
        raise HTTPException(status_code=404, detail="No trains found for this route")

    if user_id and user_id in booked_users and algo is not None:
        predictions = [algo.predict(user_id, tid) for tid in route_trains]
        predictions.sort(key=lambda x: x.est, reverse=True)
        ranked = [p.iid for p in predictions[:top_n]]
    else:
        ranked = sorted(
            route_trains,
            key=lambda tid: (-(train_mean_rating.get(tid, 0.0) or 0.0), tid),
        )[:top_n]

    return {
        "source": src,
        "destination": dst,
        "userId": user_id,
        "recommendations": [
            _format_train_details(tid)
            for tid in ranked
        ],
    }
