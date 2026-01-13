import requests
import pandas as pd
from surprise import Dataset, Reader, SVD
from fastapi import FastAPI, HTTPException
import os
import time
from typing import Optional

app = FastAPI()

DATA_SERVICE_URL = os.getenv("DATA_SERVICE_URL", "http://data-service:8000")

flight_name_map = {}
flight_route_map = {}
flight_mean_rating = {}
booked_users = set()
algo = None
all_flight_ids = []

@app.on_event("startup")
def load_and_train_model():
    global flight_name_map, flight_route_map, flight_mean_rating, booked_users, algo, all_flight_ids

    for _ in range(10):
        try:
            users = requests.get(f"{DATA_SERVICE_URL}/users").json()
            flights = requests.get(f"{DATA_SERVICE_URL}/flights").json()
            break
        except Exception as e:
            print(f"Waiting for data-service... {e}")
            time.sleep(3)
    else:
        raise RuntimeError("data-service did not respond in time")

    flight_name_map = {f["flightNumber"]: f.get("airline", "Unknown") for f in flights if "flightNumber" in f}
    flight_route_map = {
        f["flightNumber"]: {
            "airline": f.get("airline", "Unknown"),
            "source": f.get("source"),
            "destination": f.get("destination"),
            "departure": f.get("departure"),
            "arrival": f.get("arrival"),
        }
        for f in flights
        if "flightNumber" in f
    }
    all_flight_ids = [f["flightNumber"] for f in flights if "flightNumber" in f]

    bookings = [
        u for u in users
        if u.get("interactionType") == "Book" and u.get("flightNumber") and u.get("userId") and u.get("rating") not in (None, "", "NaN")
    ]

    df = pd.DataFrame(bookings)
    df = df.dropna(subset=["userId", "flightNumber", "rating"])
    df["rating"] = pd.to_numeric(df["rating"], errors="coerce")
    df = df.dropna(subset=["rating"])

    if not df.empty:
        flight_mean_rating = df.groupby("flightNumber")["rating"].mean().to_dict()

    reader = Reader(rating_scale=(1, 5))
    data = Dataset.load_from_df(df[["userId", "flightNumber", "rating"]], reader)
    trainset = data.build_full_trainset()

    algo = SVD()
    algo.fit(trainset)

    booked_users.update(df["userId"])

@app.get("/recommend/{user_id}")
def recommend(user_id: str):
    global flight_name_map, flight_route_map, booked_users, algo, all_flight_ids

    if not user_id.strip():
        raise HTTPException(status_code=422, detail="User ID cannot be empty")

    if user_id not in booked_users:
        top = all_flight_ids[:10]
        return {
            "recommendations": [
                {
                    "flightNumber": fid,
                    "flightName": _format_flight_name(fid),
                    **_format_flight_details(fid),
                }
                for fid in top
            ]
        }

    predictions = [algo.predict(user_id, fid) for fid in all_flight_ids]
    predictions.sort(key=lambda x: x.est, reverse=True)

    return {
        "recommendations": [
            {
                "flightNumber": pred.iid,
                "flightName": _format_flight_name(pred.iid),
                **_format_flight_details(pred.iid),
            }
            for pred in predictions[:10]
        ]
    }


def _format_flight_details(flight_number: str) -> dict:
    meta = flight_route_map.get(flight_number) or {}
    # Keep keys stable and optional; callers can ignore.
    return {
        "airline": meta.get("airline"),
        "source": meta.get("source"),
        "destination": meta.get("destination"),
        "departure": meta.get("departure"),
        "arrival": meta.get("arrival"),
    }


def _format_flight_name(flight_number: str) -> str:
    meta = flight_route_map.get(flight_number) or {}
    airline = meta.get("airline") or flight_name_map.get(flight_number, "Unknown")
    source = meta.get("source")
    destination = meta.get("destination")
    if source and destination:
        return f"{airline} {flight_number} {source}→{destination}"
    return f"{airline} {flight_number}"


def _format_route_item(flight_number: str) -> dict:
    meta = flight_route_map.get(flight_number) or {}
    return {
        "id": flight_number,
        "name": _format_flight_name(flight_number),
        "mode": "air",
        "source": meta.get("source"),
        "destination": meta.get("destination"),
        "departure": meta.get("departure"),
        "arrival": meta.get("arrival"),
        "meta": {
            "airline": meta.get("airline"),
        },
    }

@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/recommend-route")
def recommend_route(source: str, destination: str, user_id: Optional[str] = None, top_n: int = 10):
    """Route-based recommendations.

    Inputs:
    - source: airport code (e.g. SFO)
    - destination: airport code (e.g. JFK)
    - user_id: optional user id for personalization
    - top_n: number of results
    """
    global flight_route_map, flight_mean_rating, booked_users, algo

    src = (source or "").strip()
    dst = (destination or "").strip()
    if not src or not dst:
        raise HTTPException(status_code=422, detail="source and destination are required")

    # Filter flights to the requested route.
    route_flights = [
        fid
        for fid, meta in flight_route_map.items()
        if (meta.get("source") or "").lower() == src.lower() and (meta.get("destination") or "").lower() == dst.lower()
    ]

    if not route_flights:
        raise HTTPException(status_code=404, detail="No flights found for this route")

    # Personalized ranking if user_id is known + model is trained.
    if user_id and user_id in booked_users and algo is not None:
        predictions = [algo.predict(user_id, fid) for fid in route_flights]
        predictions.sort(key=lambda x: x.est, reverse=True)
        ranked = [p.iid for p in predictions[:top_n]]
    else:
        # Fallback: rank by mean rating from historical bookings, then stable by id.
        ranked = sorted(
            route_flights,
            key=lambda fid: (
                -(flight_mean_rating.get(fid, 0.0) or 0.0),
                fid,
            ),
        )[:top_n]

    return {
        "source": src,
        "destination": dst,
        "userId": user_id,
        "recommendations": [_format_route_item(fid) for fid in ranked],
    }
