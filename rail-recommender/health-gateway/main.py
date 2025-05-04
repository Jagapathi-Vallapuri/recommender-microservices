from fastapi import FastAPI
import docker
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
client = docker.DockerClient(base_url='unix://var/run/docker.sock')

@app.get("/service-health")
def get_health():
    containers = {
        "data-service": "unavailable",
        "recommender-service": "unavailable",
    }

    for name in containers:
        try:
            container = client.containers.get(f"rail-recommender-{name}-1")
            health = container.attrs.get("State", {}).get("Health", {}).get("Status", "no healthcheck")
            containers[name] = health
        except Exception as e:
            containers[name] = f"error: {str(e)}"

    return containers


@app.get("/health")
async def health():
    return {"status": "healthy"}
