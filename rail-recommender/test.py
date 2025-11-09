import requests

# Define service endpoints
services = {
    "recommender-service": {
        "base_url": "http://localhost:8001",
        "routes": [
            "/health",
            "/recommend/40630"
        ]
    },
    "health-gateway": {
        "base_url": "http://localhost:8050",
        "routes": [
            "/service-health"
        ]
    }
}

def test_service(name, base_url, routes):
    print(f"\nTesting {name}:")
    for route in routes:
        try:
            url = f"{base_url}{route}"
            res = requests.get(url, timeout=5)
            print(f"- GET {route} -> {res.status_code}")
            try:
                print(f"  Response: {res.json()}")
            except Exception:
                print("  Response not JSON decodable")
        except requests.exceptions.RequestException as e:
            print(f"- GET {route} -> ERROR: {e}")

# Run tests
if __name__ == "__main__":
    print("RailRecommender Service Test")
    for service_name, service_info in services.items():
        test_service(service_name, service_info["base_url"], service_info["routes"])
