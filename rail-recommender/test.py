import requests


BASE_URLS = {
    "data": "http://localhost:8000",
    "recommender": "http://localhost:8001",
    "health": "http://localhost:8050",
}

def test_data_service():
    print("\n Testing data-service:")
    try:
        print("- Health:", requests.get(f"{BASE_URLS['data']}/health").json())
        print("- Get trains:", requests.get(f"{BASE_URLS['data']}/trains?limit=2").json())
        print("- Get by source:", requests.get(f"{BASE_URLS['data']}/trains/source/KOTTAYAM").json())
        print("- Get by route:", requests.get(f"{BASE_URLS['data']}/trains/route/DHARMABAD/KODINAR").json())
    except Exception as e:
        print(" data-service error:", str(e))


def test_recommender_service():
    print("\n Testing recommender-service:")
    try:
        print("- Health:", requests.get(f"{BASE_URLS['recommender']}/health").json())
        
        train_number = "40630"  
        r = requests.get(f"{BASE_URLS['recommender']}/recommend/{train_number}")
        if r.status_code == 200:
            print("- Recommend:", r.json())
        else:
            print(f"- Recommend [{r.status_code}]:", r.text)
    except Exception as e:
        print(" recommender-service error:", str(e))


def test_health_gateway():
    print("\n Testing health-gateway:")
    try:
        print("- Service Health:", requests.get(f"{BASE_URLS['health']}/service-health").json())
    except Exception as e:
        print(" health-gateway error:", str(e))


if __name__ == "__main__":
    print(" RailRecommender Service Test")
    test_data_service()
    test_recommender_service()
    test_health_gateway()
