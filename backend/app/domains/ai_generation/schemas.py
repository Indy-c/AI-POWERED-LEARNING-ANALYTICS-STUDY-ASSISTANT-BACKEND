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

# One generated quiz question
class QuizQuestion(BaseModel):
    question: str
    choices: list[str]
    correct_answer: str

# Quiz questions returned for a study document
class QuizGenerationResponse(BaseModel):
    document_id: int
    questions: list[QuizQuestion]
    provider: str