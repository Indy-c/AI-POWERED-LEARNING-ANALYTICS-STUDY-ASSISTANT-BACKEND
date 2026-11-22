import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rate_limit import limiter
from app.domains.ai_generation.schemas import (
    FlashcardsResponse,
    QuizGenerationResponse,
    QuizQuestion,
    StudyMaterialsResponse,
    SummaryResponse,
)
from app.domains.ai_generation.service import (
    GeminiNotConfigured,
    generate_basic_flashcards,
    generate_basic_quiz,
    generate_basic_summary,
    generate_gemini_flashcards,
    generate_gemini_quiz,
    generate_gemini_summary,
)
from app.domains.auth.dependencies import get_current_user
from app.domains.documents.dependencies import get_document_or_404, get_study_text
from app.domains.quizzes.service import (
    iter_document_quizzes,
    prepare_quiz_questions,
    save_generated_quiz,
)
from app.domains.users.model import User

# Router for AI-generated learning resources
router = APIRouter(prefix="/ai", tags=["AI Generation"])
logger = logging.getLogger(__name__)


def _public_quiz_questions(questions: list[dict]) -> list[QuizQuestion]:
    if not questions:
        raise ValueError("Quiz contains no questions")

    public = []
    for item in questions:
        question = QuizQuestion.model_validate(item)
        correct_index = item.get("correct_choice_index")
        if (
            len(question.choices) < 2
            or not all(text.strip() for text in (question.question, *question.choices))
            or type(correct_index) is not int
            or not 0 <= correct_index < len(question.choices)
        ):
            raise ValueError("Quiz contains an unusable question")
        public.append(question)
    return public


def _latest_saved_quiz(db: Session, document_id: int, user_id: int) -> QuizGenerationResponse | None:
    for quiz in iter_document_quizzes(db, document_id, user_id):
        try:
            return QuizGenerationResponse(
                quiz_id=quiz.id,
                document_id=document_id,
                questions=_public_quiz_questions(quiz.questions),
                provider=quiz.provider or "saved",
            )
        except ValueError:
            logger.warning("Ignoring an invalid saved quiz (id=%s)", quiz.id)
    return None

@router.get("/documents/{document_id}/study-materials", response_model=StudyMaterialsResponse)
def read_study_materials(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = get_document_or_404(db, document_id, current_user)
    return StudyMaterialsResponse(
        summary=document.summary_material,
        flashcards=document.flashcard_material,
        quiz=_latest_saved_quiz(db, document.id, current_user.id),
        roadmap=document.roadmap_material,
    )

# Generate and save a summary for a document
@router.post("/documents/{document_id}/summary", response_model=SummaryResponse)
@limiter.limit("5/hour") 
def generate_summary(
    request: Request,
    document_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):   
    document = get_document_or_404(db, document_id, current_user)
    document_text = get_study_text(db, document)

    try:
        summary = generate_gemini_summary(document_text)
        provider = "gemini"
    except ValueError as exc:
        if not isinstance(exc, GeminiNotConfigured) and document.summary_material is not None:
            raise HTTPException(status_code=502, detail="We couldn't generate a new summary. Please try again.") from exc
        summary = generate_basic_summary(document_text)
        provider = "basic"
    response = SummaryResponse(document_id=document.id, summary=summary, provider=provider)
    document.summary_material = response.model_dump(mode="json")
    db.commit()
    return response

# Generate and save flashcards for a document
@router.post("/documents/{document_id}/flashcards", response_model=FlashcardsResponse)
@limiter.limit("5/hour")
def generate_flashcards(
    request: Request,
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = get_document_or_404(db, document_id, current_user)
    document_text = get_study_text(db, document)

    try: 
        flashcards = generate_gemini_flashcards(document_text)
        provider = "gemini"
    except ValueError as exc:
        if not isinstance(exc, GeminiNotConfigured) and document.flashcard_material is not None:
            raise HTTPException(status_code=502, detail="We couldn't generate new flashcards. Please try again.") from exc
        flashcards = generate_basic_flashcards(document_text)
        provider = "basic"
    response = FlashcardsResponse(
        document_id=document.id,
        flashcards=flashcards,
        provider=provider,
    )
    document.flashcard_material = response.model_dump(mode="json")
    db.commit()
    return response

# Generate and save a quiz for a document
@router.post("/documents/{document_id}/quiz", response_model=QuizGenerationResponse)
@limiter.limit("5/hour")
def generate_quiz(
    request: Request,
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = get_document_or_404(db, document_id, current_user)
    document_text = get_study_text(db, document)

    try:
        questions = generate_gemini_quiz(document_text)
        prepared_questions = prepare_quiz_questions(questions)
        provider = "gemini"
    except ValueError as exc:
        if not isinstance(exc, GeminiNotConfigured) and _latest_saved_quiz(db, document.id, current_user.id):
            raise HTTPException(status_code=502, detail="We couldn't generate a new quiz. Please try again.") from exc
        questions = generate_basic_quiz(document_text)
        prepared_questions = prepare_quiz_questions(questions)
        provider = "basic"

    try:
        public_questions = _public_quiz_questions(prepared_questions)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="We couldn't generate a usable quiz. Please try again.") from exc
    quiz = save_generated_quiz(
        db,
        user_id=current_user.id,
        document_id=document.id,
        questions=prepared_questions,
        provider=provider,
    )

    return QuizGenerationResponse(
        quiz_id=quiz.id,
        document_id=quiz.document_id,
        questions=public_questions,
        provider=provider,
    )
