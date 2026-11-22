import logging

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.domains.documents.model import Document
from app.domains.documents.pdf_text import PDFExtractionBusy, PDFExtractionError
from app.domains.documents.service import download_document_bytes, get_or_extract_document_text, get_user_document
from app.domains.users.model import User

logger = logging.getLogger(__name__)
_MISSING_PDF_DETAIL = "Document file is missing. Please upload the PDF again."


def get_document_or_404(db: Session, document_id: int, current_user: User) -> Document:
    document = get_user_document(db, document_id, current_user)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return document


def get_original_pdf(document: Document) -> bytes:
    try:
        return download_document_bytes(document)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_MISSING_PDF_DETAIL) from exc


def get_study_text(db: Session, document: Document, *, allow_empty: bool = False) -> str:
    try:
        text = get_or_extract_document_text(db, document)
    except PDFExtractionBusy as exc:
        raise HTTPException(status_code=503, detail="PDF preparation is busy. Please try again shortly.") from exc
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_MISSING_PDF_DETAIL,
        ) from exc
    except PDFExtractionError as exc:
        logger.warning("Could not prepare document %s", document.id, exc_info=True)
        raise HTTPException(status_code=422, detail={
            "code": "pdf_extraction_failed",
            "message": "We couldn't read this PDF. Try again or upload another copy.",
        }) from exc

    if not allow_empty and not text.strip():
        raise HTTPException(status_code=422, detail={
            "code": "no_selectable_text",
            "message": "This PDF has no selectable text. Try uploading a text-based version.",
        })
    return text
