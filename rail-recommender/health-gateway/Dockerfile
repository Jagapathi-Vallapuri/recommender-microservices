FROM python:3.9-slim

WORKDIR /app
COPY main.py .

RUN pip install fastapi[all] docker

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8050"]
