from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.storage import get_supabase_client
from app.core.config import settings

from app.domains.documents.model import Document
from app.domains.users.model import User

# Folder where uploaded PDF files are stored locally 
UPLOAD_DIR = Path("uploads/documents")

# Save an uploaded PDF to Supabase storage and create its database record
async def save_uploaded_document(
        db: Session,
        file: UploadFile,
        current_user: User,
    ) -> Document:
    file_extension = Path(file.filename or "").suffix.lower()
    stored_filename = f"{uuid4()}{file_extension}"
    storage_path = f"users/{current_user.id}/documents/{stored_filename}"
    file_bytes = await file.read() 
    
    #adding size check
    max_file_size = 10 * 1024 * 1024 
    if len(file_bytes) > max_file_size:
        raise ValueError("PDF File must be 10MB or smaller for this version")
    if file_extension != ".pdf":
        raise ValueError("Only PDF files are allowed for this version!")

    supabase = get_supabase_client()
    supabase.storage.from_(settings.supabase_storage_bucket).upload(
        storage_path,
        file_bytes,
        {"content-type": file.content_type or "application/pdf"},
    )

    document = Document(
        owner_id = current_user.id, 
        original_filename = file.filename or stored_filename, 
        stored_filename = stored_filename, 
        file_path = storage_path, 
        content_type = file.content_type or "application/pdf", 
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    return document

# Download a document file from Supabase Storage
def download_document_bytes(document: Document) -> bytes:
    if not document.file_path:
        raise FileNotFoundError("PDF file was not found")
    
    supabase = get_supabase_client()
    return supabase.storage.from_(settings.supabase_storage_bucket).download(
        document.file_path
    )

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
    document.extracted_text = extracted_text
    document.processing_status = "processed"
    db.commit()
    db.refresh(document)

    return document    

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