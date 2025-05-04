import requests

# Define service endpoints
services = {
    "data-service": {
        "base_url": "http://localhost:8100",
        "routes": [
            "/health",
            "/users",
            "/flights"
        ]
    },
    "recommender-service": {
        "base_url": "http://localhost:8101",
        "routes": [
            "/health",
            "/recommend/c1141bce-0092-4326-a995-29d73cf07a47"  
        ]
    },
    "health-gateway": {
        "base_url": "http://localhost:8150",
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
for service_name, service_info in services.items():
    test_service(service_name, service_info["base_url"], service_info["routes"])
