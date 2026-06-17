from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.domains.auth.dependencies import get_current_user
from app.domains.documents.pdf_text import extract_pdf_text_from_bytes
from app.domains.documents.service import download_document_bytes, get_user_document, save_document_text
from app.domains.roadmap.schemas import RoadmapResponse
from app.domains.roadmap.service import generate_basic_roadmap, generate_gemini_roadmap
from app.domains.users.model import User

# Routes for study roadmap generation
router = APIRouter(prefix="/roadmap", tags=["Roadmap"])

# Generate a basic study roadmap from one document
@router.post("/documents/{document_id}", response_model=RoadmapResponse)
def generate_document_roadmap(
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
        file_bytes = download_document_bytes(document)
        document_text = extract_pdf_text_from_bytes(file_bytes)
        save_document_text(db, document, document_text)

    try:
        steps = generate_gemini_roadmap(document_text)
        provider = "gemini"
    except ValueError:
        steps = generate_basic_roadmap(document_text)
        provider = "basic"

    return RoadmapResponse(
        document_id=document.id,
        steps=steps,
        provider=provider,
    )