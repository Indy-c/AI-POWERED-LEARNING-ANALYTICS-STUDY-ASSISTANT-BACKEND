from pydantic import BaseModel

# Summary returned for a study document
class SummaryResponse(BaseModel):
    document_id: int
    summary: str
    provider: str

# One generated flashcard
class FlashcardItem(BaseModel):
    question: str
    answer: str

# Flashcards returned for a study document
class FlashcardsResponse(BaseModel):
    document_id: int
    flashcards: list[FlashcardItem]
    provider: str