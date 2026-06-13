from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.domains.ai_generation.schemas import (
    FlashcardsResponse,
    QuizGenerationResponse,
    SummaryResponse,
)
from app.domains.ai_generation.service import (
    generate_basic_flashcards,
    generate_basic_quiz,
    generate_basic_summary,
    generate_gemini_summary,
)
from app.domains.auth.dependencies import get_current_user
from app.domains.documents.pdf_text import extract_pdf_text
from app.domains.documents.service import get_user_document, save_document_text
from app.domains.users.model import User

# Router for AI-generated learning resources
router = APIRouter(prefix="/ai", tags=["AI Generation"])

# Generate a temporary basic summary for a document
@router.post("/documents/{document_id}/summary", response_model=SummaryResponse)
def generate_summary(
    document_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = get_user_document(db, document_id, current_user)
    if document is None: 
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    document_text = document.extracted_text
    if not document_text:
        try: 
            document_text = extract_pdf_text(document.file_path)
        except FileNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Document file is missing. Please upload the PDF again.",
            )
        
        save_document_text(db, document, document_text)

    try:
        summary = generate_gemini_summary(document_text)
        provider = "gemini"
    except ValueError:
        summary = generate_basic_summary(document_text)
        provider = "basic"
    return SummaryResponse(document_id=document.id, summary=summary, provider=provider)

# Generate temporary basic flashcards for a document
@router.post("/documents/{document_id}/flashcards", response_model=FlashcardsResponse)
def generate_flashcards(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = get_user_document(db, document_id, current_user)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    document_text = document.extracted_text
    if not document_text:
        try:
            document_text = extract_pdf_text(document.file_path)
        except FileNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Document file is missing. Please upload the PDF again.",
            )
        
        save_document_text(db, document, document_text)

    flashcards = generate_basic_flashcards(document_text)
    return FlashcardsResponse(
        document_id=document.id,
        flashcards=flashcards,
        provider="basic",
    )

# Generate temporary basic quiz questions for a document
@router.post("/documents/{document_id}/quiz", response_model=QuizGenerationResponse)
def generate_quiz(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = get_user_document(db, document_id, current_user)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    
    document_text = document.extracted_text
    if not document_text:
        try:
            document_text = extract_pdf_text(document.file_path)
        except FileNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Document file is missing. Please upload the PDF again.",
            )

        save_document_text(db, document, document_text)

    questions = generate_basic_quiz(document_text)
    return QuizGenerationResponse(
        document_id=document.id,
        questions=questions,
        provider="basic",
    )