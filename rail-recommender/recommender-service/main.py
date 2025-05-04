from fastapi import FastAPI, HTTPException
from pymongo import MongoClient
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import requests
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
DATA_SERVICE_URL = os.getenv("DATA_SERVICE_URL")

client = MongoClient(MONGODB_URI)
db = client[DATABASE_NAME]
collection = db.trains

def create_train_matrix():
    """Create feature matrix for recommendation"""
    trains = list(collection.find({}, {'_id': 0}))
    df = pd.DataFrame(trains)
    
    features = pd.get_dummies(df[['source', 'destination', 'station_name']].fillna('Unknown'))
    return df, features

@app.get("/recommend/{train_number}")
async def recommend_trains(train_number: str, top_n: int = 5):
    try:
        response = requests.get(f"{DATA_SERVICE_URL}/trains/{train_number}")
        if response.status_code != 200:
            raise HTTPException(status_code=404, detail="Train not found")
        
        df, features = create_train_matrix()
        
        try:
            train_number = int(train_number)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid train number format")

        train_idx = df[df['train_number'] == train_number].index

        if len(train_idx) == 0:
            raise HTTPException(status_code=404, detail="Train not found in dataset")
        train_idx = train_idx[0]
        
        similarity_matrix = cosine_similarity(features)
        similar_indices = np.argsort(similarity_matrix[train_idx])[::-1][1:top_n+1]
        
        recommendations = df.iloc[similar_indices][['train_number', 'train_name', 'source', 'destination', 'station_name', 'departure']].to_dict('records')
        
        return {
            "train_number": train_number,
            "recommendations": recommendations
        }
    
    except Exception as e:
        import traceback
        traceback.print_exc()  # helps debug in logs
        raise HTTPException(status_code=500, detail=str(e) or "Unknown error occurred")

    
@app.get("/health")
async def health():
    return {"status": "healthy"}
