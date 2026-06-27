from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.domains.documents.model import Document
from app.domains.flashcards.model import Flashcard
from app.domains.quizzes.model import QuizAttempt
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

def test_delete_current_user_account_removes_user_data_and_files(monkeypatch):
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
    flashcard = Flashcard(
        id=1,
        user_id=1,
        document_id=1,
        question="Question?",
        answer="Answer",
    )
    quiz_attempt = QuizAttempt(
        id=1,
        user_id=1,
        document_id=1,
        total_questions=2,
        correct_answers=1,
        score_percentage=50.0,
    )

    db.add_all([user, document, flashcard, quiz_attempt])
    db.commit()

    monkeypatch.setattr(
        "app.domains.users.service.get_supabase_client",
        lambda: create_fake_supabase_client(removed_paths),
    )

    delete_current_user_account(db, user)

    assert removed_paths == ["users/1/documents/test.pdf"]
    assert db.get(Flashcard, 1) is None
    assert db.get(QuizAttempt, 1) is None
    assert db.get(Document, 1) is None
    assert db.get(User, 1) is None