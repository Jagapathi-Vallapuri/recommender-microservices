# Recommender Microservices

This repository contains two independently runnable, microservice-based recommender systems:

-  **Rail Recommender**
-  **Airline Recommender**

Each project follows a modular architecture using FastAPI, Postgres, Docker, and a Vite-based React frontend.

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

## `gateway-server/`

A lightweight API gateway that routes requests to either the airline or rail recommender service.

### Run

1. Start the airline and rail stacks in their folders (they publish recommender ports to localhost).
2. Start the gateway:

```bash
cd gateway-server
docker compose up -d --build
```

### Endpoints

- `GET /health`
- `GET /recommend-route?mode=air|rail&source=...&destination=...&user_id=...&top_n=...`
- `GET /recommend/{user_id}?mode=air|rail&top_n=...`

By default the gateway container proxies to:
- airline recommender: `http://host.docker.internal:8101`
- rail recommender: `http://host.docker.internal:8001`

Override via env vars: `AIRLINE_RECOMMENDER_URL`, `RAIL_RECOMMENDER_URL`.

---

## `client-frontend/`

A simple React (Vite) client UI that sends requests to the gateway-server.

### Run locally (recommended)

```bash
cd client-frontend
npm install
npm run dev
```

By default it calls `http://localhost:9000`. To override:

```bash
set VITE_GATEWAY_URL=http://localhost:9000
```

---
