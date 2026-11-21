from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rate_limit import limiter
from app.domains.auth.dependencies import get_current_user
from app.domains.quizzes.schemas import QuizAttemptRead, SavedQuizSubmitRequest
from app.domains.quizzes.service import (
    calculate_score_percentage,
    get_user_quiz,
    grade_saved_quiz,
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
    submission: SavedQuizSubmitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    quiz = get_user_quiz(db, submission.quiz_id, current_user.id)
    if quiz is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quiz not found",
        )

    try:
        correct_answers = grade_saved_quiz(quiz.questions, submission.answers)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    total_questions = len(quiz.questions)
    return save_quiz_attempt(
        db=db,
        current_user=current_user,
        document_id=quiz.document_id,
        total_questions=total_questions,
        correct_answers=correct_answers,
        score_percentage=calculate_score_percentage(correct_answers, total_questions),
    )

# List quiz attempts for the current user
@router.get("/attempts", response_model=list[QuizAttemptRead])
def list_my_quiz_attempts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return list_user_quiz_attempts(db, current_user)