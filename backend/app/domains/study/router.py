from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.routing import APIRoute
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rate_limit import limiter
from app.domains.ai_generation.service import GeminiNotConfigured
from app.domains.auth.dependencies import get_current_user
from app.domains.study import service
from app.domains.study.analytics import read_analytics
from app.domains.study.generation import StudyGenerationError
from app.domains.study.schemas import (
    Feedback, Outline, OutlineEdit, PartRead, PracticeRequest, QuizSubmission, SectionRead, StudyAnalytics,
)
from app.domains.users.model import User


class StudyRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def handle(request: Request):
            try:
                return await handler(request)
            except GeminiNotConfigured:
                raise HTTPException(503, "Guided generation is not available right now.") from None
            except StudyGenerationError:
                raise HTTPException(
                    502, "We couldn't verify the generated study material. Please try again.",
                ) from None

        return handle


router = APIRouter(tags=["Guided study"], route_class=StudyRoute)
generation_limit = limiter.shared_limit("12/hour", scope="guided-study-generation")


@router.get("/documents/{document_id}/study", response_model=Outline)
def get_outline(document_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.read_outline(db, document_id, user.id)


@router.post("/documents/{document_id}/study/prepare", response_model=Outline)
@limiter.limit("20/hour")
def prepare_outline(
    request: Request, document_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    return service.prepare_outline(db, document_id, user.id)


@router.patch("/documents/{document_id}/study/sections", response_model=Outline)
def edit_outline(
    document_id: int, edit: OutlineEdit, db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    return service.edit_outline(db, document_id, user.id, edit)


@router.post("/study/sections/{section_id}/prepare", response_model=SectionRead)
@limiter.limit("24/hour")
def prepare_section(
    request: Request, section_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    return service.prepare_section(db, section_id, user.id)


@router.get("/study/parts/{part_id}", response_model=PartRead)
def get_part(part_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.read_part(db, part_id, user.id)


@router.post("/study/parts/{part_id}/lesson", response_model=PartRead)
@generation_limit
def prepare_lesson(
    request: Request, part_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    return service.prepare_lesson(db, part_id, user.id)


@router.post("/study/parts/{part_id}/practice", response_model=PartRead)
@generation_limit
def prepare_practice(
    request: Request, part_id: int, practice: PracticeRequest,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    return service.prepare_practice(db, part_id, user.id, practice.retry)


@router.post("/study/quizzes/{quiz_id}/submit", response_model=Feedback)
@limiter.limit("30/hour")
def submit_practice(
    request: Request, quiz_id: int, submission: QuizSubmission,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    return service.submit_practice(db, quiz_id, user.id, submission)


@router.get("/analytics/study", response_model=StudyAnalytics)
def get_study_analytics(
    document_id: int | None = Query(None, ge=1), timezone: str = Query("UTC", max_length=64),
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    return read_analytics(db, user.id, document_id, timezone)
