from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.domains.auth.dependencies import get_current_user
from app.domains.documents.schemas import DocumentRead
from app.domains.documents.service import save_uploaded_document
from app.domains.users.model import User

# Routes for study document management
router = APIRouter(prefix="/documents", tags=["Documents"])

# Upload a PDF study document
@router.post("/upload", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...), 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try: 
        return await save_uploaded_document(db, file, current_user)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) 