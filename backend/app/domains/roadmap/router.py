from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.domains.ai_generation.service import GeminiNotConfigured
from app.domains.auth.dependencies import get_current_user
from app.domains.documents.dependencies import get_document_or_404, get_study_text
from app.domains.roadmap.schemas import RoadmapResponse
from app.domains.roadmap.service import generate_basic_roadmap, generate_gemini_roadmap
from app.domains.users.model import User

# Routes for study roadmap generation
router = APIRouter(prefix="/roadmap", tags=["Roadmap"])

# Generate and save a study roadmap from one document
@router.post("/documents/{document_id}", response_model=RoadmapResponse)
def generate_document_roadmap(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = get_document_or_404(db, document_id, current_user)
    document_text = get_study_text(db, document)

    try:
        steps = generate_gemini_roadmap(document_text)
        provider = "gemini"
    except ValueError as exc:
        if not isinstance(exc, GeminiNotConfigured) and document.roadmap_material is not None:
            raise HTTPException(status_code=502, detail="We couldn't generate a new roadmap. Please try again.") from exc
        steps = generate_basic_roadmap(document_text)
        provider = "basic"

    response = RoadmapResponse(
        document_id=document.id,
        steps=steps,
        provider=provider,
    )
    document.roadmap_material = response.model_dump(mode="json")
    db.commit()
    return response
