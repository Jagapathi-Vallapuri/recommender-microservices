from fastapi import FastAPI, HTTPException
from pymongo import MongoClient
from pydantic import BaseModel
from typing import Optional
import pandas as pd
import os
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MONGODB_URI = os.getenv("MONGODB_URI")
DATABASE_NAME = os.getenv("DATABASE_NAME")
client = MongoClient(MONGODB_URI)
db = client[DATABASE_NAME]
collection = db.trains

class TrainData(BaseModel):
    train_number: str
    train_name: str
    station_name: str
    departure: str
    source: Optional[str]
    destination: Optional[str]

@app.on_event("startup")
async def startup_event():
    if collection.count_documents({}) == 0:
        try:
            df = pd.read_csv("datasets/train_data.csv")
            print(f"Loaded CSV with {len(df)} records")
            records = df.to_dict('records')
            collection.insert_many(records)
            print("Synthetic data loaded into MongoDB")
        except FileNotFoundError:
            print("Synthetic data CSV not found. Please generate it first.")
        except Exception as e:
            print(f"Error loading data into MongoDB: {str(e)}")

@app.get("/trains")
async def get_trains(limit: int = 100):
    trains = list(collection.find({}, {'_id': 0}).limit(limit))
    return trains

@app.post("/trains")
async def create_train(train: TrainData):
    result = collection.insert_one(train.dict())
    return {"id": str(result.inserted_id)}

@app.get("/trains/{train_number}")
async def get_train(train_number: str):
    try:
        train_number_int = int(train_number)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid train number format")
    
    train = collection.find_one({"train_number": train_number_int}, {'_id': 0})
    if train:
        return train
    raise HTTPException(status_code=404, detail="Train not found")


@app.get("/trains/source/{source}")
async def get_trains_by_source(source: str):
    trains = list(collection.find({"source": {"$regex": f"^{source}$", "$options": "i"}}, {'_id': 0}))
    return trains

@app.get("/trains/route/{source}/{destination}")
async def get_trains_by_route(source: str, destination: str):
    trains = list(collection.find(
        {
            "source": {"$regex": f"^{source}$", "$options": "i"},
            "destination": {"$regex": f"^{destination}$", "$options": "i"}
        },
        {'_id': 0}
    ))
    if trains:
        return trains
    raise HTTPException(status_code=404, detail="No trains found for this route")

@app.get("/health")
async def health():
    return {"status": "healthy"}
