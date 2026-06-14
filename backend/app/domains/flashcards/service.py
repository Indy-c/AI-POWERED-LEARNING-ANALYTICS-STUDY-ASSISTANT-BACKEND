from sqlalchemy.orm import Session

from app.domains.documents.service import get_user_document
from app.domains.flashcards.model import Flashcard
from app.domains.flashcards.schemas import FlashcardCreate
from app.domains.users.model import User

# Save one flashcard for the current user
def save_flashcard(
        db: Session,
        current_user: User,
        flashcard_data: FlashcardCreate,
) -> Flashcard | None:
    document = get_user_document(db, flashcard_data.document_id, current_user)
    if document is None:
        return None

    flashcard = Flashcard(
        user_id = current_user.id,
        document_id = flashcard_data.document_id,
        question=flashcard_data.question,
        answer=flashcard_data.answer,
    )
    db.add(flashcard)
    db.commit()
    db.refresh(flashcard)

    return flashcard

# List saved flashcards for the current user
def list_user_flashcards(db: Session, current_user: User) -> list[Flashcard]:
    return (
        db.query(Flashcard)
        .filter(Flashcard.user_id == current_user.id)
        .order_by(Flashcard.created_at.desc())
        .all()
    )