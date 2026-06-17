from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.domains.auth.dependencies import get_current_user
from app.domains.flashcards.schemas import FlashcardCreate, FlashcardRead
from app.domains.flashcards.service import list_user_flashcards, save_flashcard, delete_user_flashcard
from app.domains.users.model import User

# Routes for saved flashcards
router = APIRouter(prefix="/flashcards", tags=["Flashcards"])

# Save one flashcard for the current user
@router.post("", response_model=FlashcardRead, status_code=status.HTTP_201_CREATED)
def create_flashcard(
    flashcard_data: FlashcardCreate, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    flashcard = save_flashcard(db, current_user, flashcard_data)
    if flashcard is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found", 
        )
    
    return flashcard

# List saved flashcards for the current user
@router.get("", response_model=list[FlashcardRead])
def list_my_flashcards(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return list_user_flashcards(db, current_user)

# Delete one flashcard owned by the current user
@router.delete("/{flashcard_id}")
def delete_flashcard(
    flashcard_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deleted = delete_user_flashcard(db, flashcard_id, current_user)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Flashcard not found",
        )

    return {"detail": "Flashcard deleted successfully"}
