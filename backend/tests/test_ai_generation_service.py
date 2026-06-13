from app.domains.ai_generation.service import (
    generate_basic_flashcards,
    generate_basic_quiz,
    generate_basic_summary,
)

def test_generate_basic_summary_cleans_whitespace():
    document_text = "This   is\n\nstudy   material."
    summary = generate_basic_summary(document_text)

    assert summary == "This is study material."

def test_generate_basic_flashcards_returns_question_and_answer():
    flashcards = generate_basic_flashcards("Photosynthesis helps plants make food.")

    assert len(flashcards) == 1
    assert flashcards[0]["question"] == "What is the main idea of this document?"
    assert "Photosynthesis" in flashcards[0]["answer"]

def test_generate_basic_quiz_returns_question_choices_and_answer():
    questions = generate_basic_quiz("Cash flow is important for small businesses.")

    assert len(questions) == 1
    assert questions[0]["question"] == "What is this study material mainly about?"
    assert len(questions[0]["choices"]) == 4
    assert questions[0]["correct_answer"] in questions[0]["choices"]