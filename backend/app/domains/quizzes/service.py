from app.domains.quizzes.schemas import QuizAnswerSubmission

# Count how many submitted answers are correct
def count_correct_answers(answers: list[QuizAnswerSubmission]) -> int:
    return sum(
        answer.selected_answer == answer.correct_answer
        for answer in answers
    )

# Calculate quiz score percentage
def calculate_score_percentage(correct_answers: int, total_questions: int) -> float:
    if total_questions == 0:
        return 0.0
    
    return round((correct_answers / total_questions) * 100, 2)