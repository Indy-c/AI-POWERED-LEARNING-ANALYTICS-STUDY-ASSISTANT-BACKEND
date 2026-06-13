from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rate_limit import limiter
from app.domains.auth.dependencies import get_current_user
from app.domains.documents.service import get_user_document
from app.domains.quizzes.schemas import QuizAttemptRead, QuizSubmitRequest
from app.domains.quizzes.service import (
    calculate_score_percentage,
    count_correct_answers,
    list_user_quiz_attempts,
    save_quiz_attempt,
)
from app.domains.users.model import User

# Routes for quiz attempts and scoring
router = APIRouter(prefix="/quizzes", tags=["Quizzes"])

# Submit quiz answers and calculate score
@router.post("/submit", response_model=QuizAttemptRead)
@limiter.limit("30/hour")
def submit_quiz(
    request: Request,
    submission: QuizSubmitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = get_user_document(db, submission.document_id, current_user)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    
    total_questions = len(submission.answers)
    correct_answers = count_correct_answers(submission.answers)
    score_percentage = calculate_score_percentage(correct_answers, total_questions)

    return save_quiz_attempt(
        db=db,
        current_user=current_user,
        document_id=submission.document_id,
        total_questions=total_questions,
        correct_answers=correct_answers,
        score_percentage=score_percentage,
    )

# List quiz attempts for the current user
@router.get("/attempts", response_model=list[QuizAttemptRead])
def list_my_quiz_attempts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return list_user_quiz_attempts(db, current_user)