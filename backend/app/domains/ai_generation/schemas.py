from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from app.domains.roadmap.schemas import RoadmapResponse

NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

# Summary returned for a study document
class SummaryResponse(BaseModel):
    document_id: int
    summary: NonEmptyText
    provider: str

# One generated flashcard
class FlashcardItem(BaseModel):
    question: NonEmptyText
    answer: NonEmptyText

# Flashcards returned for a study document
class FlashcardsResponse(BaseModel):
    document_id: int
    flashcards: list[FlashcardItem] = Field(min_length=1)
    provider: str

# One generated quiz question
class QuizQuestion(BaseModel):
    question: str
    choices: list[str]

# Quiz questions returned for a study document
class QuizGenerationResponse(BaseModel):
    quiz_id: int
    document_id: int
    questions: list[QuizQuestion]
    provider: str


class StudyMaterialsResponse(BaseModel):
    summary: SummaryResponse | None = None
    flashcards: FlashcardsResponse | None = None
    quiz: QuizGenerationResponse | None = None
    roadmap: RoadmapResponse | None = None
