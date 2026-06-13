from app.domains.quizzes.schemas import QuizAnswerSubmission
from app.domains.quizzes.service import calculate_score_percentage, count_correct_answers

def test_count_correct_answers():
    answers = [
        QuizAnswerSubmission(
            question="Question 1",
            selected_answer="A",
            correct_answer="A",
        ),
        QuizAnswerSubmission(
            question="Question 2",
            selected_answer="B",
            correct_answer="C",
        ),
    ]

    assert count_correct_answers(answers) == 1

def test_calculate_score_percentage():
    assert calculate_score_percentage(correct_answers=1, total_questions=2) == 50.0

def test_calculate_score_percentage_with_zero_questions():
    assert calculate_score_percentage(correct_answers=0, total_questions=0) == 0.0