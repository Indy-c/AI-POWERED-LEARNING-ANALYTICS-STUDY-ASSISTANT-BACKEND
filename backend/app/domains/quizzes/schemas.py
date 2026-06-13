from pydantic import BaseModel
from datetime import datetime

# One answer submitted by a student
class QuizAnswerSubmission(BaseModel):
    question: str
    selected_answer: str
    correct_answer: str

# Quiz submission request from the frontend
class QuizSubmitRequest(BaseModel):
    document_id: int
    answers: list[QuizAnswerSubmission]

# Quiz scoring result returned by the API
class QuizScoreResponse(BaseModel):
    document_id: int
    total_questions: int
    correct_answers: int
    score_percentage: float

# Saved quiz attempt returned by the API
class QuizAttemptRead(BaseModel):
    id: int
    document_id: int
    total_questions: int
    correct_answers: int
    score_percentage: float
    created_at: datetime

    model_config = {"from_attributes": True}