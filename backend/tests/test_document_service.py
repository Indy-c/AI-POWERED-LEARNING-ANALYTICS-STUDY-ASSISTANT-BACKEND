from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.domains.documents.model import Document
from app.domains.documents.service import delete_user_document
from app.domains.users.model import User

def create_test_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine)

    return TestingSessionLocal()

def create_fake_supabase_client(removed_paths: list[str]):
    def remove(paths: list[str]):
        removed_paths.extend(paths)

    return SimpleNamespace(
        storage=SimpleNamespace(
            from_=lambda bucket: SimpleNamespace(remove=remove)
        )
    )

def test_delete_user_document_removes_file_and_database_record(monkeypatch):
    db = create_test_db()
    removed_paths: list[str] = []

    user = User(
        id=1,
        email="student@example.com",
        full_name="Test Student",
        hashed_password="hashed",
    )
    document = Document(
        id=1,
        owner_id=1,
        original_filename="test.pdf",
        stored_filename="test.pdf",
        file_path="users/1/documents/test.pdf",
    )

    db.add_all([user, document])
    db.commit()

    monkeypatch.setattr(
        "app.domains.documents.service.get_supabase_client",
        lambda: create_fake_supabase_client(removed_paths),
    )

    deleted = delete_user_document(db, document_id=1, current_user=user)

    assert deleted is True
    assert removed_paths == ["users/1/documents/test.pdf"]
    assert db.get(Document, 1) is None

def test_delete_user_document_rejects_other_users_document(monkeypatch):
    db = create_test_db()
    removed_paths: list[str] = []

    current_user = User(
        id=1,
        email="student@example.com",
        full_name="Test Student",
        hashed_password="hashed",
    )
    other_user_document = Document(
        id=1,
        owner_id=2,
        original_filename="test.pdf",
        stored_filename="test.pdf",
        file_path="users/2/documents/test.pdf",
    )

    db.add_all([current_user, other_user_document])
    db.commit()

    monkeypatch.setattr(
        "app.domains.documents.service.get_supabase_client",
        lambda: create_fake_supabase_client(removed_paths),
    )

    deleted = delete_user_document(db, document_id=1, current_user=current_user)

    assert deleted is False
    assert removed_paths == []
    assert db.get(Document, 1) is not None