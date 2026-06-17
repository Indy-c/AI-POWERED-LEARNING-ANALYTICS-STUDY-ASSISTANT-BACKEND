from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.domains.documents.model import Document
from app.domains.flashcards.model import Flashcard
from app.domains.flashcards.service import delete_user_flashcard
from app.domains.users.model import User

def create_test_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine)

    return TestingSessionLocal()

def test_delete_user_flashcard_removes_owned_flashcard():
    db = create_test_db()

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
    flashcard = Flashcard(
        id=1,
        user_id=1,
        document_id=1,
        question="Question?",
        answer="Answer",
    )

    db.add_all([user, document, flashcard])
    db.commit()

    deleted = delete_user_flashcard(db, flashcard_id=1, current_user=user)

    assert deleted is True
    assert db.get(Flashcard, 1) is None

def test_delete_user_flashcard_rejects_other_users_flashcard():
    db = create_test_db()

    current_user = User(
        id=1,
        email="student@example.com",
        full_name="Test Student",
        hashed_password="hashed",
    )
    other_user_flashcard = Flashcard(
        id=1,
        user_id=2,
        document_id=1,
        question="Question?",
        answer="Answer",
    )

    db.add_all([current_user, other_user_flashcard])
    db.commit()

    deleted = delete_user_flashcard(db, flashcard_id=1, current_user=current_user)

    assert deleted is False
    assert db.get(Flashcard, 1) is not None