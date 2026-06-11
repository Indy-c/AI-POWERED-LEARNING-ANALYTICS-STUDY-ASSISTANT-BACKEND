from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.domains.documents.model import Document
from app.domains.users.model import User

# Folder where uploaded PDF files are stored locally 
UPLOAD_DIR = Path("uploads/documents")

# Save an uploaded PDF and create its database record
async def save_uploaded_document(
        db: Session,
        file: UploadFile,
        current_user: User,
    ) -> Document:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    file_extension = Path(file.filename or "").suffix.lower()
    stored_filename = f"{uuid4()}{file_extension}"
    file_path = UPLOAD_DIR / stored_filename
    file_bytes = await file.read() 
    
    #adding size check
    max_file_size = 10 * 1024 * 1024 
    if len(file_bytes) > max_file_size:
        raise ValueError("PDF File must be 10MB or smaller for this version")
    if file_extension != ".pdf":
        raise ValueError("Only PDF files are allowed for this version!")
    file_path.write_bytes(file_bytes)

    document = Document(
        owner_id = current_user.id, 
        original_filename = file.filename or stored_filename, 
        stored_filename = stored_filename, 
        file_path = str(file_path), 
        content_type = file.content_type or "application/pdf", 
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    return document