import logging
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from starlette.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from storage3.exceptions import StorageApiError

from app.core.storage import get_supabase_client
from app.core.config import settings

from app.domains.documents.model import Document
from app.domains.documents.pdf_text import PDFExtractionError, extract_pdf_text_from_bytes
from app.domains.users.model import User

logger = logging.getLogger(__name__)
_MAX_PDF_BYTES = 10 * 1024 * 1024

# Folder where uploaded PDF files are stored locally 
UPLOAD_DIR = Path("uploads/documents")

# Save an uploaded PDF to Supabase storage and create its database record
async def save_uploaded_document(
        db: Session,
        file: UploadFile,
        current_user: User,
    ) -> Document:
    filename = file.filename
    content_type = file.content_type or "application/pdf"
    file_extension = Path(filename or "").suffix.lower()
    if file_extension != ".pdf":
        raise ValueError("Only PDF files are allowed for this version!")

    file_bytes = await file.read(_MAX_PDF_BYTES + 1)
    if len(file_bytes) > _MAX_PDF_BYTES:
        raise ValueError("PDF File must be 10MB or smaller for this version")

    owner_id = current_user.id
    if not (db.new or db.dirty or db.deleted):
        # Release the read transaction opened by authentication before external work.
        db.rollback()
    stored_filename = f"{uuid4()}{file_extension}"
    storage_path = f"users/{owner_id}/documents/{stored_filename}"
    extracted_text, processing_status = await run_in_threadpool(
        _prepare_uploaded_pdf, storage_path, file_bytes, content_type,
    )

    document = Document(
        owner_id=owner_id,
        original_filename=filename or stored_filename,
        stored_filename=stored_filename,
        file_path=storage_path,
        content_type=content_type,
        extracted_text=extracted_text or None,
        processing_status=processing_status,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def _prepare_uploaded_pdf(storage_path: str, file_bytes: bytes, content_type: str) -> tuple[str | None, str]:
    try:
        extracted_text = extract_pdf_text_from_bytes(file_bytes)
        processing_status = "processed" if extracted_text else "no_text"
    except PDFExtractionError:
        logger.warning("Could not extract text from uploaded PDF", exc_info=True)
        extracted_text = None
        processing_status = "extraction_failed"

    supabase = get_supabase_client()
    supabase.storage.from_(settings.supabase_storage_bucket).upload(
        storage_path,
        file_bytes,
        {"content-type": content_type},
    )
    return extracted_text, processing_status

# Download a document file from Supabase Storage
def download_document_bytes(document: Document) -> bytes:
    if not document.file_path:
        raise FileNotFoundError("PDF file was not found")
    
    supabase = get_supabase_client()
    try:
        return supabase.storage.from_(settings.supabase_storage_bucket).download(
            document.file_path
        )
    except StorageApiError as exc:
        if (
            str(exc.status) == "404"
            and exc.code == "not_found"
            and exc.message == "Object not found"
        ):
            raise FileNotFoundError("PDF file was not found") from exc
        raise

# List documents uploaded by the current user 
def list_user_documents(db: Session, current_user: User) -> list[Document]:
    return (
        db.query(Document)
        .filter(Document.owner_id == current_user.id)
        .order_by(Document.created_at.desc())
        .all()
    )

# Find one document owned by current user
def get_user_document(
    db: Session,
    document_id: int,
    current_user: User,
) -> Document | None:
    return (
        db.query(Document)
        .filter(Document.id == document_id, Document.owner_id == current_user.id)
        .first()
    )

# Save extracted text for a document
def save_document_text(
        db: Session, 
        document: Document, 
        extracted_text: str
) -> Document:
    document.extracted_text = extracted_text or None
    document.processing_status = "processed" if extracted_text else "no_text"
    db.commit()
    db.refresh(document)

    return document


def get_or_extract_document_text(db: Session, document: Document) -> str:
    if document.extracted_text or document.processing_status == "no_text":
        return document.extracted_text or ""

    file_bytes = download_document_bytes(document)
    try:
        extracted_text = extract_pdf_text_from_bytes(file_bytes)
    except PDFExtractionError:
        document.processing_status = "extraction_failed"
        db.commit()
        raise

    save_document_text(db, document, extracted_text)
    return extracted_text

# Delete a document file from Supabase Storage and remove its database record
def delete_user_document(db: Session, document_id: int, current_user: User) -> bool:
    document = get_user_document(db, document_id, current_user)
    if document is None:
        return False
    
    if document.file_path:
        supabase = get_supabase_client()
        supabase.storage.from_(settings.supabase_storage_bucket).remove(
            [document.file_path]
        )

    db.delete(document)
    db.commit()

    return True
