from fastapi import FastAPI
from app.core.config import settings

app = FastAPI(title = settings.app_name, description = "API for AI Learning Assistant", version = "1.0.0")

@app.get("/")
def health_check():
    return {"message": f"{settings.app_name} is running!", "status": "healthy"}