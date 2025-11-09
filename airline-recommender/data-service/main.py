from fastapi import FastAPI, HTTPException
from pymongo import MongoClient
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import pandas as pd
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "flight_data")
client = MongoClient(MONGODB_URI)
db = client[DATABASE_NAME]
flights_collection = db.flights
interactions_collection = db.user_interactions

@app.on_event("startup")
async def load_csv_to_mongo():
    if flights_collection.count_documents({}) == 0:
        try:
            flights_df = pd.read_csv("dataset/synthetic_flights.csv")
            flights_collection.insert_many(flights_df.to_dict("records"))
            print(f"Loaded {len(flights_df)} flights.")
        except Exception as e:
            print(f"Failed to load flights: {e}")

    if interactions_collection.count_documents({}) == 0:
        try:
            interactions_df = pd.read_csv("dataset/synthetic_user_interactions.csv")
            interactions_df = interactions_df.dropna(subset=["flightNumber"]) 
            interactions_collection.insert_many(interactions_df.to_dict("records"))
            print(f"Loaded {len(interactions_df)} user interactions.")
        except Exception as e:
            print(f"Failed to load user interactions: {e}")

@app.get("/flights")
async def get_flights(limit: int = 100):
    return list(flights_collection.find({}, {'_id': 0}).limit(limit))

import math

@app.get("/users")
async def get_users(limit: int = 100):
    users = list(interactions_collection.find({}, {'_id': 0}).limit(limit))
    
    for user in users:
        for k, v in user.items():
            if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                user[k] = None

    return users


@app.get("/health")
def health():
    return {"status": "healthy"}
