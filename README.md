# Recommender Microservices

This repository contains two independently runnable, microservice-based recommender systems:

-  **Rail Recommender**
-  **Airline Recommender**

Each project follows a modular architecture using FastAPI, MongoDB, Docker, and a Vite-based React frontend.

---

##  Projects Overview

### `rail-recommender/`

Recommends train journeys using route, station, and schedule features.  
**Components:**
- `data-service/`: Ingests and serves train data.
- `recommender-service/`: Computes recommendations using cosine similarity.
- `frontend/`: React + Vite UI for monitoring health of recommener and data services.
- `health-gateway/`: Monitors microservice health via Docker socket.

### `airline-recommender/`

Recommends flights based on synthetic user interactions.  
**Components:**
- `data-service/`: Loads flight and interaction data.
- `recommender-service/`: Uses collaborative filtering or similarity for recommendations.
- `frontend/`: React + Vite UI for monitoring health of recommender and data services.
- `health-gateway/`: Monitors microservice health via Docker socket.

---
