from fastapi import FastAPI, Request
from app.core.config import settings
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi import _rate_limit_exceeded_handler

from app.domains.users.router import router as users_router
from app.domains.auth.router import router as auth_router
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