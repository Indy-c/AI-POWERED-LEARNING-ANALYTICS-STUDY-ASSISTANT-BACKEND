from sqlalchemy import func
from sqlalchemy.orm import Session

from app.domains.documents.model import Document
from app.domains.flashcards.model import Flashcard
from app.domains.quizzes.model import QuizAttempt
from app.domains.users.model import User

# Build dashboard analytics from existing document, flashcard, and quiz data
def get_user_analytics_summary(db: Session, current_user: User) -> dict[str, int | float]:
    total_documents = (
        db.query(Document)
        .filter(Document.owner_id == current_user.id)
        .count()
    )

    total_flashcards = (
        db.query(Flashcard)
        .filter(Flashcard.user_id == current_user.id)
        .count()
    )

    quiz_attempts_query = db.query(QuizAttempt).filter(
        QuizAttempt.user_id == current_user.id
    )

    total_quiz_attempts = quiz_attempts_query.count()

    average_score = (
        quiz_attempts_query
        .with_entities(func.avg(QuizAttempt.score_percentage))
        .scalar()
        or 0.0
    )

    best_score = (
        quiz_attempts_query
        .with_entities(func.max(QuizAttempt.score_percentage))
        .scalar()
        or 0.0
    )

    latest_attempt = (
        quiz_attempts_query
        .order_by(QuizAttempt.created_at.desc())
        .first()
    )

    latest_score = latest_attempt.score_percentage if latest_attempt else 0.0

    return {
        "total_documents": total_documents,
        "total_quiz_attempts": total_quiz_attempts,
        "total_flashcards": total_flashcards,
        "average_score": round(float(average_score), 2),
        "latest_score": round(float(latest_score), 2),
        "best_score": round(float(best_score), 2),
    }