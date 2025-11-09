import requests
import pandas as pd
from surprise import Dataset, Reader, SVD
from fastapi import FastAPI, HTTPException
import os
import time

app = FastAPI()

DATA_SERVICE_URL = os.getenv("DATA_SERVICE_URL", "http://data-service:8000")

flight_name_map = {}
booked_users = set()
algo = None
all_flight_ids = []

@app.on_event("startup")
def load_and_train_model():
    global flight_name_map, booked_users, algo, all_flight_ids

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
    all_flight_ids = [f["flightNumber"] for f in flights if "flightNumber" in f]

    bookings = [
        u for u in users
        if u.get("interactionType") == "Book" and u.get("flightNumber") and u.get("userId") and u.get("rating") not in (None, "", "NaN")
    ]

    df = pd.DataFrame(bookings)
    df = df.dropna(subset=["userId", "flightNumber", "rating"])
    df["rating"] = pd.to_numeric(df["rating"], errors="coerce")
    df = df.dropna(subset=["rating"])

    reader = Reader(rating_scale=(1, 5))
    data = Dataset.load_from_df(df[["userId", "flightNumber", "rating"]], reader)
    trainset = data.build_full_trainset()

    algo = SVD()
    algo.fit(trainset)

    booked_users.update(df["userId"])

@app.get("/recommend/{user_id}")
def recommend(user_id: str):
    global flight_name_map, booked_users, algo, all_flight_ids

    if not user_id.strip():
        raise HTTPException(status_code=422, detail="User ID cannot be empty")

    if user_id not in booked_users:
        top = all_flight_ids[:10]
        return {
            "recommendations": [
                {"flightNumber": fid, "flightName": f"{flight_name_map.get(fid, 'Unknown')} {fid}"}
                for fid in top
            ]
        }

    predictions = [algo.predict(user_id, fid) for fid in all_flight_ids]
    predictions.sort(key=lambda x: x.est, reverse=True)

    return {
        "recommendations": [
            {"flightNumber": pred.iid, "flightName": f"{flight_name_map.get(pred.iid, 'Unknown')} {pred.iid}"}
            for pred in predictions[:10]
        ]
    }

@app.get("/health")
def health():
    return {"status": "healthy"}
