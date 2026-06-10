from fastapi import FastAPI

app = FastAPI(title = "AI Learning Assistant API", description = "API for AI Learning Assistant", version = "1.0.0")

@app.get("/")
def health_check():
    return {"message": "AI Learning Assistant API is running!", "status": "healthy"}