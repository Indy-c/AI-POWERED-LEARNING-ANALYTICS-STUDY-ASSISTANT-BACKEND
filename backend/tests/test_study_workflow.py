from types import SimpleNamespace

import fitz
import pytest
from fastapi import Header
from fastapi.testclient import TestClient
from google.genai.errors import ClientError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.domains.auth.dependencies import get_current_user
from app.domains.documents.model import Document
from app.domains.quizzes.model import Quiz
from app.domains.users.model import User
from app.main import app


@pytest.fixture
def workspace(monkeypatch):
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        for user_id in (1, 2):
            db.add(User(id=user_id, email=f"user{user_id}@example.com", full_name="Test user", hashed_password="test"))
        db.commit()

    files = {}

    def upload(path, content, _options):
        files[path] = content

    def storage_client():
        bucket = SimpleNamespace(upload=upload, download=files.__getitem__)
        return SimpleNamespace(storage=SimpleNamespace(from_=lambda _: bucket))

    def test_db():
        with Session(engine) as db:
            yield db

    def test_user(x_test_user: int = Header(1)):
        return User(id=x_test_user)

    monkeypatch.setattr("app.domains.documents.service.get_supabase_client", storage_client)
    monkeypatch.setitem(app.dependency_overrides, get_db, test_db)
    monkeypatch.setitem(app.dependency_overrides, get_current_user, test_user)
    app.state.limiter.reset()
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, engine
    app.state.limiter.reset()
    engine.dispose()


def pdf_bytes(text="Photosynthesis uses light."):
    with fitz.open() as pdf:
        page = pdf.new_page()
        if text:
            page.insert_text((72, 72), text)
        return pdf.tobytes()


def upload_pdf(client, content):
    response = client.post("/documents/upload", files={"file": ("notes.pdf", content, "application/pdf")})
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.parametrize("content,status,has_text", [
    pytest.param(pdf_bytes(), "processed", True, id="selectable-text"),
    pytest.param(pdf_bytes(""), "no_text", False, id="blank-pdf"),
    pytest.param(b"Invalid PDF file", "extraction_failed", False, id="invalid-pdf"),
])
def test_upload_reports_preparation_result(workspace, content, status, has_text):
    client, engine = workspace
    document = upload_pdf(client, content)
    assert document["processing_status"] == status
    assert document["has_extracted_text"] is has_text
    with Session(engine) as db:
        saved = db.get(Document, document["id"])
        assert saved.extracted_text == ("Photosynthesis uses light." if has_text else None)


def test_owner_can_open_original_pdf_even_without_selectable_text(workspace):
    client, _ = workspace
    original_bytes = pdf_bytes("")
    document = upload_pdf(client, original_bytes)
    assert document["has_extracted_text"] is False

    url = f"/documents/{document['id']}/file"
    assert client.get(url, headers={"X-Test-User": "2"}).status_code == 404
    response = client.get(url)
    assert response.status_code == 200
    assert response.content == original_bytes


@pytest.mark.parametrize("path", ["/ai/documents/{id}/summary", "/roadmap/documents/{id}"])
def test_generation_rejects_unreadable_text_without_calling_gemini(workspace, monkeypatch, path):
    client, _ = workspace
    document = upload_pdf(client, pdf_bytes(""))

    def unexpected_generation(_text):
        raise AssertionError("Gemini must not receive an empty document")

    monkeypatch.setattr("app.domains.ai_generation.router.generate_gemini_summary", unexpected_generation)
    monkeypatch.setattr("app.domains.roadmap.router.generate_gemini_roadmap", unexpected_generation)
    response = client.post(path.format(id=document["id"]))
    assert response.status_code == 422, response.text
    assert response.json()["detail"]["code"] == "no_selectable_text"


def test_materials_restore_for_older_upload_and_survive_failed_regeneration(workspace, monkeypatch):
    client, engine = workspace
    document_id = upload_pdf(client, pdf_bytes())["id"]
    base = f"/ai/documents/{document_id}"
    with Session(engine) as db:
        document = db.get(Document, document_id)
        document.processing_status = "uploaded"
        document.extracted_text = None
        db.commit()

    def summary(text):
        assert text == "Photosynthesis uses light."
        return "Plants use light."

    monkeypatch.setattr("app.domains.ai_generation.router.generate_gemini_summary", summary)
    monkeypatch.setattr("app.domains.ai_generation.router.generate_gemini_flashcards", lambda _: [
        {"question": "What is used?", "answer": "Light"},
    ])
    monkeypatch.setattr("app.domains.ai_generation.router.generate_gemini_quiz", lambda _: [
        {"question": "What is used?", "choices": ["Light", "Dark"], "correct_answer": "Light"},
    ])
    monkeypatch.setattr("app.domains.roadmap.router.generate_gemini_roadmap", lambda _: [
        {"title": "Light", "description": "Review how plants use light."},
    ])

    assert client.get(f"{base}/study-materials").json() == dict.fromkeys(("summary", "flashcards", "quiz", "roadmap"))
    saved = {}
    for kind, url in (
        ("summary", f"{base}/summary"), ("flashcards", f"{base}/flashcards"),
        ("quiz", f"{base}/quiz"), ("roadmap", f"/roadmap/documents/{document_id}"),
    ):
        response = client.post(url)
        assert response.status_code == 200, response.text
        saved[kind] = response.json()

    def broken_summary(_text):
        raise RuntimeError("Upstream unavailable")

    monkeypatch.setattr("app.domains.ai_generation.router.generate_gemini_summary", broken_summary)
    assert client.post(f"{base}/summary").status_code == 500
    restored = client.get(f"{base}/study-materials").json()
    assert restored == saved
    assert restored["quiz"]["questions"] == [{"question": "What is used?", "choices": ["Light", "Dark"]}]
    assert client.get(f"{base}/study-materials", headers={"X-Test-User": "2"}).status_code == 404

    monkeypatch.setattr("app.domains.ai_generation.router.generate_gemini_summary", lambda _: "Updated summary.")
    regenerated = client.post(f"{base}/summary").json()
    assert client.get(f"{base}/study-materials").json() == {**restored, "summary": regenerated}

    quiz_score = client.post("/quizzes/submit", json={
        "quiz_id": restored["quiz"]["quiz_id"],
        "answers": [{"question_index": 0, "selected_choice_index": 0}],
    })
    assert quiz_score.status_code == 200, quiz_score.text
    assert quiz_score.json()["correct_answers"] == 1


def test_existing_quiz_is_restored_without_regeneration(workspace):
    client, engine = workspace
    document_id = upload_pdf(client, pdf_bytes())["id"]
    with Session(engine) as db:
        quiz = Quiz(user_id=1, document_id=document_id, questions=[
            {"question": "Select light", "choices": ["Light", "Dark"], "correct_choice_index": 0},
        ])
        db.add(quiz)
        db.commit()
        quiz_id = quiz.id

    response = client.get(f"/ai/documents/{document_id}/study-materials")
    assert response.status_code == 200, response.text
    assert response.json()["quiz"]["quiz_id"] == quiz_id
    assert response.json()["quiz"]["questions"] == [{"question": "Select light", "choices": ["Light", "Dark"]}]


def test_malformed_legacy_quiz_does_not_hide_saved_materials(workspace, monkeypatch):
    client, engine = workspace
    document_id = upload_pdf(client, pdf_bytes())["id"]
    base = f"/ai/documents/{document_id}"
    monkeypatch.setattr("app.domains.ai_generation.router.generate_gemini_summary", lambda _: "Saved summary.")
    assert client.post(f"{base}/summary").status_code == 200
    with Session(engine) as db:
        db.add(Quiz(user_id=1, document_id=document_id, questions=[
            {"question": "Valid quiz", "choices": ["A", "B"], "correct_choice_index": 0},
        ]))
        db.add(Quiz(user_id=1, document_id=document_id, questions=[
            {"question": 123, "choices": ["A", "B"], "correct_choice_index": 0},
        ]))
        db.commit()

    response = client.get(f"{base}/study-materials")
    assert response.status_code == 200, response.text
    assert response.json()["summary"]["summary"] == "Saved summary."
    assert response.json()["quiz"]["questions"] == [{"question": "Valid quiz", "choices": ["A", "B"]}]


def test_empty_provider_summary_does_not_replace_saved_summary(workspace, monkeypatch):
    client, _ = workspace
    document_id = upload_pdf(client, pdf_bytes())["id"]
    base = f"/ai/documents/{document_id}"
    generator = "app.domains.ai_generation.router.generate_gemini_summary"
    monkeypatch.setattr(generator, lambda _: "Saved Gemini summary.")
    saved = client.post(f"{base}/summary").json()

    def empty_summary(_text):
        raise ValueError("Gemini returned an empty summary")

    monkeypatch.setattr(generator, empty_summary)
    assert client.post(f"{base}/summary").status_code == 502
    assert client.get(f"{base}/study-materials").json()["summary"] == saved


def test_provider_rate_limit_preserves_saved_material_and_returns_friendly_detail(workspace, monkeypatch):
    client, _ = workspace
    document_id = upload_pdf(client, pdf_bytes())["id"]
    base = f"/ai/documents/{document_id}"
    generator = "app.domains.ai_generation.router.generate_gemini_summary"
    monkeypatch.setattr(generator, lambda _: "Previously saved summary.")
    saved = client.post(f"{base}/summary").json()

    def rate_limited(_text):
        raise ClientError(429, {"error": {"message": "Internal provider details"}})

    monkeypatch.setattr(generator, rate_limited)
    response = client.post(f"{base}/summary")
    assert response.status_code == 429
    assert response.json()["detail"] == "You've reached the generation limit. Try again later."
    assert client.get(f"{base}/study-materials").json()["summary"] == saved


def test_reloading_saved_material_is_not_rate_limited_like_generation(workspace, monkeypatch):
    client, _ = workspace
    document_id = upload_pdf(client, pdf_bytes())["id"]
    base = f"/ai/documents/{document_id}"
    monkeypatch.setattr("app.domains.ai_generation.router.generate_gemini_summary", lambda _: "Saved summary.")
    for _ in range(5):
        assert client.post(f"{base}/summary").status_code == 200

    limited = client.post(f"{base}/summary")
    assert limited.status_code == 429
    assert limited.json()["detail"] == "Too many requests. Please try again later."
    response = client.get(f"{base}/study-materials")
    assert response.status_code == 200
    assert response.json()["summary"]["summary"] == "Saved summary."


def test_unusable_quiz_does_not_replace_saved_quiz(workspace, monkeypatch):
    client, _ = workspace
    document_id = upload_pdf(client, pdf_bytes())["id"]
    base = f"/ai/documents/{document_id}"
    generator = "app.domains.ai_generation.router.generate_gemini_quiz"
    monkeypatch.setattr(generator, lambda _: [
        {"question": "Which?", "choices": ["Light", "Dark"], "correct_answer": "Light"},
    ])
    response = client.post(f"{base}/quiz")
    assert response.status_code == 200
    saved = response.json()

    monkeypatch.setattr(generator, lambda _: [
        {"question": "Which?", "choices": ["Light"], "correct_answer": "Light"},
    ])
    assert client.post(f"{base}/quiz").status_code == 502
    assert client.get(f"{base}/study-materials").json()["quiz"] == saved
