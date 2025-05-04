from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import docker

app = FastAPI()
client = docker.DockerClient(base_url="unix://var/run/docker.sock")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8551"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SERVICE_NAMES = [
    "airline-recommender-data-service-1",
    "airline-recommender-recommender-service-1",
]

@app.get("/service-health")
def get_service_health():
    status = {}
    for name in SERVICE_NAMES:
        try:
            container = client.containers.get(name)
            health = container.attrs.get("State", {}).get("Health", {}).get("Status", "unknown")
            short_name = "-".join(name.split("-")[2:-1])
            status[short_name] = health
        except Exception as e:
            short_name = "-".join(name.split("-")[2:-1])
            status[short_name] = f"error: {str(e)}"
    return status
