import os
import sys
import requests


RECOMMENDER_BASE_URL = os.getenv("RECOMMENDER_BASE_URL", "http://localhost:8101").rstrip("/")
HEALTH_GATEWAY_BASE_URL = os.getenv("HEALTH_GATEWAY_BASE_URL", "http://localhost:8150").rstrip("/")

# Optional: if you expose the data-service to localhost, set this (e.g. http://localhost:8000).
DATA_SERVICE_BASE_URL = os.getenv("DATA_SERVICE_BASE_URL", "").rstrip("/")

ROUTE_SOURCE = (os.getenv("ROUTE_SOURCE") or "").strip()
ROUTE_DESTINATION = (os.getenv("ROUTE_DESTINATION") or "").strip()


def _get_json(url: str, params: dict | None = None, timeout: float = 8.0):
    try:
        res = requests.get(url, params=params, timeout=timeout)
    except requests.exceptions.RequestException as e:
        raise AssertionError(f"Request failed: GET {url} params={params} error={e}")

    try:
        body = res.json()
    except Exception:
        body = res.text
    return res.status_code, body


def _assert(condition: bool, message: str):
    if not condition:
        raise AssertionError(message)


def _assert_route_item_schema(item: dict, expected_mode: str):
    required = ["id", "name", "mode", "source", "destination", "departure", "arrival", "meta"]
    missing = [k for k in required if k not in item]
    _assert(not missing, f"Missing keys {missing} in recommendation item: {item}")
    _assert(item["mode"] == expected_mode, f"Expected mode={expected_mode}, got {item.get('mode')}")
    _assert(isinstance(item["meta"], dict), "Expected meta to be an object")


def _pick_route_from_data_service() -> tuple[str, str] | None:
    if not DATA_SERVICE_BASE_URL:
        return None
    status, flights = _get_json(f"{DATA_SERVICE_BASE_URL}/flights")
    if status != 200 or not isinstance(flights, list):
        return None
    for f in flights:
        src = (f.get("source") or "").strip()
        dst = (f.get("destination") or "").strip()
        if src and dst:
            return src, dst
    return None


def _pick_route_from_recommendations(user_id: str) -> tuple[str, str] | None:
    # Airline /recommend returns items that include source/destination.
    status, body = _get_json(f"{RECOMMENDER_BASE_URL}/recommend/{user_id}")
    if status != 200 or not isinstance(body, dict):
        return None
    recs = body.get("recommendations")
    if not isinstance(recs, list):
        return None
    for item in recs:
        if not isinstance(item, dict):
            continue
        src = (item.get("source") or "").strip()
        dst = (item.get("destination") or "").strip()
        if src and dst:
            return src, dst
    return None


def _find_working_route() -> tuple[str, str] | None:
    if ROUTE_SOURCE and ROUTE_DESTINATION:
        return ROUTE_SOURCE, ROUTE_DESTINATION

    route = _pick_route_from_recommendations(os.getenv("TEST_USER_ID", "test-user"))
    if route:
        return route

    route = _pick_route_from_data_service()
    if route:
        return route

    # Fallback: probe a few common airport-code routes.
    candidates = [
        ("SFO", "JFK"),
        ("LAX", "JFK"),
        ("SEA", "SFO"),
        ("ORD", "JFK"),
        ("ATL", "MIA"),
    ]
    for src, dst in candidates:
        status, _ = _get_json(
            f"{RECOMMENDER_BASE_URL}/recommend-route",
            params={"source": src, "destination": dst, "top_n": 3},
        )
        if status == 200:
            return src, dst
    return None


def test_recommender_service():
    print("\nTesting recommender-service (airline)")

    status, body = _get_json(f"{RECOMMENDER_BASE_URL}/health")
    print(f"- GET /health -> {status}")
    _assert(status == 200, f"/health failed: {body}")

    # /recommend works for unknown users (fallback list), so a fixed id is fine.
    test_user_id = os.getenv("TEST_USER_ID", "test-user")
    status, body = _get_json(f"{RECOMMENDER_BASE_URL}/recommend/{test_user_id}")
    print(f"- GET /recommend/{{user_id}} -> {status}")
    _assert(status == 200, f"/recommend failed: {body}")
    _assert(isinstance(body, dict) and isinstance(body.get("recommendations"), list), "Invalid /recommend response")
    if body["recommendations"]:
        first = body["recommendations"][0]
        _assert("flightNumber" in first and "flightName" in first, "Unexpected /recommend item shape")

    route = _find_working_route()
    _assert(route is not None, "Could not find a working route for /recommend-route; set ROUTE_SOURCE/ROUTE_DESTINATION or expose data-service and set DATA_SERVICE_BASE_URL")
    src, dst = route

    status, body = _get_json(
        f"{RECOMMENDER_BASE_URL}/recommend-route",
        params={"source": src, "destination": dst, "top_n": 5},
    )
    print(f"- GET /recommend-route?source={src}&destination={dst} -> {status}")
    _assert(status == 200, f"/recommend-route failed: {body}")
    _assert(isinstance(body, dict), "Invalid /recommend-route response")
    _assert(isinstance(body.get("recommendations"), list), "Missing recommendations list")
    if body["recommendations"]:
        _assert_route_item_schema(body["recommendations"][0], expected_mode="air")


def test_health_gateway():
    print("\nTesting health-gateway")
    status, body = _get_json(f"{HEALTH_GATEWAY_BASE_URL}/service-health")
    print(f"- GET /service-health -> {status}")
    _assert(status == 200, f"/service-health failed: {body}")


def main():
    try:
        test_recommender_service()
        test_health_gateway()
    except AssertionError as e:
        print(f"\nTEST FAILED: {e}")
        sys.exit(1)
    print("\nAll tests passed.")


if __name__ == "__main__":
    main()
