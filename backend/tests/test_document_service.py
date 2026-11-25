import pytest
from fastapi import HTTPException
from storage3.exceptions import StorageApiError
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base, create_database_engine
from app.domains.documents.model import Document
from app.domains.documents.service import delete_user_document, download_document_bytes
from app.domains.flashcards.model import Flashcard
from app.domains.quizzes.model import Quiz, QuizAttempt
from app.domains.users.model import User
from app.domains.users.service import delete_current_user_account

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

def test_download_document_bytes_reports_missing_pdf(monkeypatch):
    def download(_path):
        raise StorageApiError("Object not found", "not_found", "404")

    fake_client = SimpleNamespace(
        storage=SimpleNamespace(
            from_=lambda _bucket: SimpleNamespace(download=download)
        )
    )
    monkeypatch.setattr(
        "app.domains.documents.service.get_supabase_client",
        lambda: fake_client,
    )

    document = Document(file_path="users/1/documents/missing.pdf")

    with pytest.raises(FileNotFoundError):
        download_document_bytes(document)

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


@pytest.mark.parametrize("delete_account", [False, True])
@pytest.mark.parametrize("dependent", [Flashcard, Quiz, QuizAttempt])
def test_delete_preserves_other_users_records_linked_to_reused_document_id(monkeypatch, delete_account, dependent):
    engine = create_database_engine("sqlite://")
    Base.metadata.create_all(engine)
    removed_paths = []
    fake_storage = lambda: create_fake_supabase_client(removed_paths)
    monkeypatch.setattr("app.domains.documents.service.get_supabase_client", fake_storage)
    monkeypatch.setattr("app.domains.users.service.get_supabase_client", fake_storage)

    with sessionmaker(bind=engine)() as db:
        owner = User(id=1, email="owner@example.com", full_name="Owner", hashed_password="demo")
        previous_owner = User(id=2, email="previous@example.com", full_name="Previous", hashed_password="demo")
        db.add_all([owner, previous_owner])
        db.flush()
        db.add(Document(id=1, owner_id=1, original_filename="new.pdf", stored_filename="new.pdf", file_path="new.pdf"))
        db.flush()
        extra = {
            Flashcard: {"question": "Q?", "answer": "A"},
            Quiz: {"questions": []},
            QuizAttempt: {"total_questions": 1, "correct_answers": 1, "score_percentage": 100},
        }
        db.add(dependent(id=1, user_id=2, document_id=1, **extra[dependent]))
        db.commit()

        with pytest.raises(HTTPException) as exc:
            if delete_account:
                delete_current_user_account(db, owner)
            else:
                delete_user_document(db, document_id=1, current_user=owner)
        assert exc.value.status_code == 409
        assert removed_paths == []
        assert db.get(Document, 1) is not None
        assert db.get(dependent, 1).user_id == 2
    engine.dispose()
