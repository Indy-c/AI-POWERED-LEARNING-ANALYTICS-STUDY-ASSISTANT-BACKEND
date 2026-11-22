from collections.abc import Iterable

from sqlalchemy.orm import Session

from app.domains.users.model import User
from app.domains.quizzes.model import Quiz, QuizAttempt
from app.domains.quizzes.schemas import QuizAnswerSubmission, QuizSelection

# Get a quiz by ID for a specific user
def get_user_quiz(db: Session, quiz_id: int, user_id: int) -> Quiz | None:
    return (
        db.query(Quiz)
        .filter(Quiz.id == quiz_id, Quiz.user_id == user_id)
        .one_or_none()
    )

def iter_document_quizzes(db: Session, document_id: int, user_id: int) -> Iterable[Quiz]:
    return (
        db.query(Quiz)
        .filter(Quiz.document_id == document_id, Quiz.user_id == user_id)
        .order_by(Quiz.id.desc())
        .yield_per(16)
    )


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

# Prepare quiz questions for saving to the database
def prepare_quiz_questions(questions: list[dict]) -> list[dict]:
    if not questions:
        raise ValueError("Quiz must contain at least one question")

    prepared_questions = []
    for item in questions:
        choices = item["choices"]
        correct_answer = item["correct_answer"]

        if choices.count(correct_answer) != 1:
            raise ValueError("Correct answer must match exactly one choice")

        prepared_questions.append({
            "question": item["question"],
            "choices": choices,
            "correct_choice_index": choices.index(correct_answer),
        })

    return prepared_questions

# Save a generated quiz to the database
def save_generated_quiz(
    db: Session,
    user_id: int,
    document_id: int,
    questions: list[dict],
    provider: str | None = None,
) -> Quiz:
    quiz = Quiz(
        user_id=user_id,
        document_id=document_id,
        questions=questions,
        provider=provider,
    )
    db.add(quiz)
    db.commit()
    db.refresh(quiz)
    return quiz

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

# Grade a saved quiz based on the user's answers
def grade_saved_quiz(
    questions: list[dict],
    answers: list[QuizSelection],
) -> int:
    correct_count = 0
    answered_questions: set[int] = set()

    for answer in answers:
        question_index = answer.question_index
        if not 0 <= question_index < len(questions):
            raise ValueError("Invalid question index")
        if question_index in answered_questions:
            raise ValueError("Question answered more than once")

        question = questions[question_index]
        choice_index = answer.selected_choice_index
        if not 0 <= choice_index < len(question["choices"]):
            raise ValueError("Invalid choice index")

        answered_questions.add(question_index)
        if choice_index == question["correct_choice_index"]:
            correct_count += 1

    return correct_count

# List quiz attempts for the current user
def list_user_quiz_attempts(db: Session, current_user: User) -> list[QuizAttempt]:
    return (
        db.query(QuizAttempt)
        .filter(QuizAttempt.user_id == current_user.id)
        .order_by(QuizAttempt.created_at.desc())
        .all()
    )
