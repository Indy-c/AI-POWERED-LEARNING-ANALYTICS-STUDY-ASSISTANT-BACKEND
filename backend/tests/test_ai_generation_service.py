import json
from types import SimpleNamespace

import pytest

from app.domains.ai_generation import service as ai_service
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

@pytest.mark.parametrize(
    ("generate", "gemini_result"),
    [
        pytest.param(ai_service.generate_gemini_summary, "Test summary", id="summary"),
        pytest.param(
            ai_service.generate_gemini_quiz,
            [
                {
                    "question": "What runs automatically after a database event?",
                    "choices": ["Trigger", "View", "Index", "Join"],
                    "correct_answer": "Trigger",
                }
            ],
            id="quiz",
        ),
    ],
)
def test_gemini_generation_covers_long_document(monkeypatch, generate, gemini_result):
    filler = "Study material. " * 625  # 10,000 characters
    document_text = (
        f"START_JOIN\n{filler}\n"
        f"MIDDLE_HAVING\n{filler}\n"
        "END_TRIGGER"
    )
    prompts = []
    response_text = (
        gemini_result if isinstance(gemini_result, str) else json.dumps(gemini_result)
    )

    def fake_generate_content(model, contents):
        prompts.append(contents)
        return SimpleNamespace(text=response_text)

    fake_client = SimpleNamespace(
        models=SimpleNamespace(generate_content=fake_generate_content)
    )
    monkeypatch.setattr(ai_service, "get_gemini_client", lambda: fake_client)

    assert generate(document_text) == gemini_result

    assert len(prompts) == 1
    sent_text = prompts[0].split("\nStudy material:\n", 1)[1].removesuffix("\n")
    assert len(sent_text) <= 12_000
    assert "START_JOIN" in sent_text
    assert "MIDDLE_HAVING" in sent_text
    assert "END_TRIGGER" in sent_text


def test_study_context_preserves_text_at_character_limit():
    document_text = " Study material\n" * 750

    assert ai_service._select_study_context(document_text) == document_text
