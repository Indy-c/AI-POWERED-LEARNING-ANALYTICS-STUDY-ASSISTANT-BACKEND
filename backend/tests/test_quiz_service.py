import pytest
from app.domains.quizzes.schemas import QuizAnswerSubmission, QuizSelection
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

def test_grade_saved_quiz_uses_stored_answer_key():
    from app.domains.quizzes.service import grade_saved_quiz

    questions = [
        {"choices": ["Mercury", "Venus", "Earth"], "correct_choice_index": 2},
        {"choices": ["Mars", "Jupiter"], "correct_choice_index": 1},
    ]
    answers = [
        QuizSelection(question_index=0, selected_choice_index=2),
        QuizSelection(question_index=1, selected_choice_index=0),
    ]

    assert grade_saved_quiz(questions, answers) == 1

def test_grade_saved_quiz_rejects_duplicate_answers():
    from app.domains.quizzes.service import grade_saved_quiz

    questions = [{"choices": ["Mercury", "Earth"], "correct_choice_index": 1}]
    selection = QuizSelection(question_index=0, selected_choice_index=1)

    with pytest.raises(ValueError):
        grade_saved_quiz(questions, [selection, selection])