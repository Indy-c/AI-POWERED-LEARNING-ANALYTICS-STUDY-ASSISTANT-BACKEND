from sqlalchemy.orm import Session

from app.domains.users.model import User
from app.domains.quizzes.model import QuizAttempt
from app.domains.quizzes.schemas import QuizAnswerSubmission

# Count how many submitted answers are correct
def count_correct_answers(answers: list[QuizAnswerSubmission]) -> int:
    return sum(
        answer.selected_answer == answer.correct_answer
        for answer in answers
    )

# Calculate quiz score percentage
def calculate_score_percentage(correct_answers: int, total_questions: int) -> float:
    if total_questions == 0:
        return 0.0
    
    return round((correct_answers / total_questions) * 100, 2)

# Save a quiz attempt result to the database
def save_quiz_attempt(
    db: Session,
    current_user: User,
    document_id: int,
    total_questions: int,
    correct_answers: int,
    score_percentage: float,
) -> QuizAttempt:
    quiz_attempt = QuizAttempt(
        user_id=current_user.id,
        document_id=document_id,
        total_questions=total_questions,
        correct_answers=correct_answers,
        score_percentage=score_percentage,
    )
    db.add(quiz_attempt)
    db.commit()
    db.refresh(quiz_attempt)

    return quiz_attempt

# List quiz attempts for the current user
def list_user_quiz_attempts(db: Session, current_user: User) -> list[QuizAttempt]:
    return (
        db.query(QuizAttempt)
        .filter(QuizAttempt.user_id == current_user.id)
        .order_by(QuizAttempt.created_at.desc())
        .all()
    )