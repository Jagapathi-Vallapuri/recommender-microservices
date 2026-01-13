import os
import asyncio
import socket
from typing import Literal, Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware


Mode = Literal["air", "rail"]

app = FastAPI(title="Recommender Gateway")


allow_origins = [o.strip() for o in os.getenv("CORS_ALLOW_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins if allow_origins != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


AIRLINE_RECOMMENDER_URL = os.getenv("AIRLINE_RECOMMENDER_URL", "http://host.docker.internal:8101").rstrip("/")
RAIL_RECOMMENDER_URL = os.getenv("RAIL_RECOMMENDER_URL", "http://host.docker.internal:8001").rstrip("/")

AIRLINE_DATA_SERVICE_URL = os.getenv("AIRLINE_DATA_SERVICE_URL", "http://airline-data-service:8000").rstrip("/")
RAIL_DATA_SERVICE_URL = os.getenv("RAIL_DATA_SERVICE_URL", "http://rail-data-service:8000").rstrip("/")

AIRLINE_POSTGRES_HOST = os.getenv("AIRLINE_POSTGRES_HOST", "airline-postgres")
AIRLINE_POSTGRES_PORT = int(os.getenv("AIRLINE_POSTGRES_PORT", "5432"))
RAIL_POSTGRES_HOST = os.getenv("RAIL_POSTGRES_HOST", "rail-postgres")
RAIL_POSTGRES_PORT = int(os.getenv("RAIL_POSTGRES_PORT", "5432"))

TIMEOUT_SECONDS = float(os.getenv("GATEWAY_TIMEOUT_SECONDS", "10"))


def _auto_detect_mode(source: str, destination: str) -> Mode:
    # Simple heuristic:
    # - Airline seeded data uses 3-letter uppercase airport codes (e.g., BOS, DEN)
    # - Rail seeded data often uses non-3-letter codes (sometimes 3-letter too, but not always)
    # Users can always override with explicit mode.
    s = (source or "").strip()
    d = (destination or "").strip()
    if len(s) == 3 and len(d) == 3 and s.isalpha() and d.isalpha() and s.upper() == s and d.upper() == d:
        return "air"
    return "rail"


def _base_url_for_mode(mode: Mode) -> str:
    return AIRLINE_RECOMMENDER_URL if mode == "air" else RAIL_RECOMMENDER_URL


async def _proxy_get(base_url: str, path: str, params: dict):
    url = f"{base_url}{path}"
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
        try:
            resp = await client.get(url, params=params)
        except httpx.RequestError as e:
            raise HTTPException(status_code=502, detail=f"Upstream unreachable: {url} ({e})")

    try:
        body = resp.json()
    except Exception:
        body = resp.text

    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=body)

    return body


async def _check_http_health(name: str, base_url: str) -> tuple[str, str]:
    url = f"{base_url.rstrip('/')}/health"
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
        try:
            resp = await client.get(url)
            if resp.status_code == 200:
                return name, "healthy"
            return name, f"unhealthy ({resp.status_code})"
        except httpx.RequestError:
            return name, "unreachable"


def _check_tcp(name: str, host: str, port: int) -> tuple[str, str]:
    try:
        with socket.create_connection((host, port), timeout=min(TIMEOUT_SECONDS, 3.0)):
            return name, "healthy"
    except OSError:
        return name, "unreachable"


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/service-health")
async def service_health():
    """Simple dashboard endpoint.

    Returns a map of service -> status. Keeps the response intentionally simple
    for the client dashboard.
    """
    checks = [
        _check_http_health("gateway-server", "http://127.0.0.1:9000"),
        _check_http_health("airline-data-service", AIRLINE_DATA_SERVICE_URL),
        _check_http_health("airline-recommender-service", AIRLINE_RECOMMENDER_URL),
        _check_http_health("rail-data-service", RAIL_DATA_SERVICE_URL),
        _check_http_health("rail-recommender-service", RAIL_RECOMMENDER_URL),
    ]

    results: dict[str, str] = {}
    for name, status in await asyncio.gather(*checks):
        results[name] = status

    for n, s in (
        _check_tcp("airline-postgres", AIRLINE_POSTGRES_HOST, AIRLINE_POSTGRES_PORT),
        _check_tcp("rail-postgres", RAIL_POSTGRES_HOST, RAIL_POSTGRES_PORT),
    ):
        results[n] = s

    return results


@app.get("/recommend-route")
async def recommend_route(
    source: str,
    destination: str,
    mode: Optional[Mode] = None,
    user_id: Optional[str] = None,
    top_n: int = 10,
):
    if not (source or "").strip() or not (destination or "").strip():
        raise HTTPException(status_code=422, detail="source and destination are required")

    chosen_mode: Mode = mode or _auto_detect_mode(source, destination)
    base_url = _base_url_for_mode(chosen_mode)

    payload = await _proxy_get(
        base_url,
        "/recommend-route",
        params={
            "source": source,
            "destination": destination,
            "user_id": user_id,
            "top_n": top_n,
        },
    )

    return {
        **(payload if isinstance(payload, dict) else {"data": payload}),
        "mode": chosen_mode,
        "upstream": base_url,
    }


@app.get("/recommend/{user_id}")
async def recommend_user(user_id: str, mode: Mode, top_n: int = 10):
    if not (user_id or "").strip():
        raise HTTPException(status_code=422, detail="user_id is required")

    base_url = _base_url_for_mode(mode)
    return await _proxy_get(base_url, f"/recommend/{user_id}", params={"top_n": top_n})
