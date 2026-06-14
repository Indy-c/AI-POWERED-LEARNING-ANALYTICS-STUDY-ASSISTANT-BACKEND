from datetime import datetime

from pydantic import BaseModel

# Flashcard data sent by the frontend
class FlashcardCreate(BaseModel):
    document_id: int
    question: str
    answer: str
    
# Saved flashcard returned by the API
class FlashcardRead(BaseModel):
    id: int
    document_id: int
    question: str
    answer: str
    created_at: datetime

    model_config = {"from_attributes": True}