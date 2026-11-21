from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.storage import get_supabase_client
from app.core.security import hash_password

from app.domains.users.model import User
from app.domains.users.schemas import UserCreate
from app.domains.documents.model import Document
from app.domains.flashcards.model import Flashcard
from app.domains.quizzes.model import QuizAttempt

# Find one user by email address to check if the email is already registered.
def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email).first()

# Create and save a new user
def create_user(db: Session, user_data: UserCreate) -> User:
    db_user = User(
        email=user_data.email,
        full_name=user_data.full_name,
        hashed_password=hash_password(user_data.password),
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return db_user

# Delete the current user and all owned data
def delete_current_user_account(db: Session, current_user: User) -> None:
    documents = (
        db.query(Document)
        .filter(Document.owner_id == current_user.id)
        .all()
    )

    file_paths = [
        document.file_path
        for document in documents
        if document.file_path
    ]
    
    if file_paths:
        supabase = get_supabase_client()
        supabase.storage.from_(settings.supabase_storage_bucket).remove(file_paths)
    
    db.query(Flashcard).filter(Flashcard.user_id == current_user.id).delete()
    db.query(QuizAttempt).filter(QuizAttempt.user_id == current_user.id).delete()
    db.query(Document).filter(Document.owner_id == current_user.id).delete()

    db.delete(current_user)
    db.commit()