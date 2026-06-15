from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.domains.analytics.schemas import AnalyticsSummary
from app.domains.analytics.service import get_user_analytics_summary
from app.domains.auth.dependencies import get_current_user
from app.domains.users.model import User

# Routes for dashboard analytics
router = APIRouter(prefix="/analytics", tags=["Analytics"])

# Get dashboard analytics for the current user
@router.get("/me", response_model=AnalyticsSummary)
def read_my_analytics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_user_analytics_summary(db, current_user)