from pydantic import BaseModel

# Dashboard analytics returned for the logged-in user

class AnalyticsSummary(BaseModel):
    total_documents: int
    total_quiz_attempts: int
    total_flashcards: int
    average_score: float
    latest_score: float
    best_score: float