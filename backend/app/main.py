from fastapi import FastAPI, Request
from app.core.config import settings
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi import _rate_limit_exceeded_handler

from app.domains.users.router import router as users_router
from app.domains.auth.router import router as auth_router
from app.domains.documents.router import router as documents_router
from app.domains.ai_generation.router import router as ai_generation_router
from app.domains.quizzes.router import router as quizzes_router
from app.domains.flashcards.router import router as flashcards_router
from app.domains.analytics.router import router as analytics_router
from app.domains.roadmap.router import router as roadmap_router
from app.core.rate_limit import limiter

app = FastAPI(title = settings.app_name, description = "API for AI Learning Assistant", version = "1.0.0")

# Register rate limiting support
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

@app.get("/")
@limiter.limit("10/minute")  # Example: limit to 10 requests per minute per IP
def health_check(request: Request):
    return {"message": f"{settings.app_name} is running!", "status": "healthy"}

# Register domain routers
app.include_router(users_router)
# Register authentication routes
app.include_router(auth_router)
# Register document routes
app.include_router(documents_router)
# Register AI generation routes
app.include_router(ai_generation_router)
# Register Quizzes routes
app.include_router(quizzes_router)
# Register flashcard routes
app.include_router(flashcards_router)
# Register analytics routes
app.include_router(analytics_router)
# Register roadmap routes
app.include_router(roadmap_router)