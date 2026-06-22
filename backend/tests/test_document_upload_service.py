import pytest
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.domains.documents.model import Document
from app.domains.documents.service import save_uploaded_document
from app.domains.users.model import User

def create_test_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine)

    return TestingSessionLocal()

class FakeUploadFile:
    def __init__(
        self,
        filename: str,
        content: bytes,
        content_type: str = "application/pdf",
    ):
        self.filename = filename
        self.content = content
        self.content_type = content_type

    async def read(self) -> bytes:
        return self.content
    
def create_fake_supabase_client(uploaded_files: list[dict]):
    def upload(path: str, file_bytes: bytes, options: dict):
        uploaded_files.append(
            {
                "path": path,
                "file_bytes": file_bytes,
                "options": options,
            }
        )

    return SimpleNamespace(
        storage=SimpleNamespace(
            from_=lambda bucket: SimpleNamespace(upload=upload)
        )
    )

@pytest.mark.anyio
async def test_save_uploaded_document_uploads_file_and_creates_record(monkeypatch):
    db = create_test_db()
    uploaded_files: list[dict] = []

    user = User(
        id = 1, 
        email = "student@example.com",
        full_name = "Test Student",
        hashed_password = "hashed",
    )
    db.add(user)
    db.commit()

    monkeypatch.setattr(
        "app.domains.documents.service.get_supabase_client",
        lambda: create_fake_supabase_client(uploaded_files),
    )

    file = FakeUploadFile(
        filename="notes.pdf",
        content=b"%PDF test content",
    )

    document = await save_uploaded_document(db, file, user)

    assert document.id == 1
    assert document.owner_id==1
    assert document.original_filename=="notes.pdf"
    assert document.stored_filename.endswith(".pdf")
    assert document.file_path.startswith("users/1/documents/")
    assert uploaded_files[0]["path"] == document.file_path
    assert uploaded_files[0]["file_bytes"] == b"%PDF test content"
    assert uploaded_files[0]["options"]["content-type"] == "application/pdf"
    assert db.get(Document, 1) is not None

@pytest.mark.anyio
async def test_save_uploaded_document_rejects_non_pdf():
    db = create_test_db()

    user = User(
        id=1,
        email="student@example.com",
        full_name="Test Student",
        hashed_password="hashed",
    )
    db.add(user)
    db.commit()

    file = FakeUploadFile(
        filename="notes.txt",
        content=b"text content",
        content_type="text/plain",
    )

    with pytest.raises(ValueError):
        await save_uploaded_document(db, file, user)

@pytest.mark.anyio
async def test_save_uploaded_document_rejects_large_file():
    db = create_test_db()

    user = User(
        id=1,
        email="student@example.com",
        full_name="Test Student",
        hashed_password="hashed",
    )
    db.add(user)
    db.commit()

    file = FakeUploadFile(
        filename="large.pdf",
        content=b"a" * (10 * 1024 * 1024 + 1),
    )

    with pytest.raises(ValueError):
        await save_uploaded_document(db, file, user)