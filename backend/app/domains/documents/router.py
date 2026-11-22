from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.domains.auth.dependencies import get_current_user
from app.domains.documents.dependencies import get_document_or_404, get_original_pdf, get_study_text
from app.domains.documents.pdf_text import PDFExtractionBusy
from app.domains.documents.schemas import DocumentRead
from app.domains.documents.service import (
    list_user_documents, 
    save_uploaded_document, 
    delete_user_document,
)
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
    except PDFExtractionBusy as exc:
        raise HTTPException(status_code=503, detail="PDF preparation is busy. Please try uploading again shortly.") from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) 
    
# GET a list of documents uploaded by the current user
@router.get("", response_model= list[DocumentRead])
def list_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return list_user_documents(db, current_user)

#GET one document owned by current user
@router.get("/{document_id}", response_model=DocumentRead)
def read_document(
    document_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_document_or_404(db, document_id, current_user)

@router.get(
    "/{document_id}/file",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {"schema": {"type": "string", "format": "binary"}}}}},
)
def read_document_file(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    document = get_document_or_404(db, document_id, current_user)
    content = get_original_pdf(document)
    filename = quote(document.original_filename or "document.pdf", safe="")
    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{filename}",
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


# Extract text from one uploaded PDF owned by the current user
@router.get("/{document_id}/text")
def read_document_text(
    document_id: int,
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user),
):
    document = get_document_or_404(db, document_id, current_user)
    extracted_text = get_study_text(db, document, allow_empty=True)
    return {
        "document_id": document.id, 
        "text": extracted_text[:5000],
        "truncated": len(extracted_text) > 5000,
        }

# Delete one document owned by the current user
@router.delete("/{document_id}")
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
): 
    deleted = delete_user_document(db, document_id, current_user)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    
    return {"detail": "Document deleted successfully"}
