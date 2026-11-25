import json
from types import SimpleNamespace

import fitz
import pytest

from .test_study_workflow import upload_pdf, workspace  # noqa: F401
from .test_study_pdf_index import _pdf


SOURCE = "WHERE filters rows. HAVING filters groups."


def study_pdf():
    with fitz.open() as pdf:
        for _ in range(10):
            pdf.new_page().insert_text((72, 72), SOURCE)
        return pdf.tobytes()


@pytest.fixture
def gemini(monkeypatch):
    calls = []

    def generate_content(*, contents, **_):
        calls.append(contents)
        if "Write a lesson for this study part" in contents:
            result = {
                "objectives": ["Filter rows", "Filter groups", "Read group totals"],
                "explanation": SOURCE,
                "example": "Use HAVING COUNT(*) > 2 to keep groups with more than two rows.",
                "sources": [{"page": 9, "quote": SOURCE}],
            }
        else:
            retry = "Previous question wording" in contents
            result = {"questions": [{
                "question": f"Decide how to filter scenario {number} ({'retry' if retry else 'first'}).",
                "topic_id": number,
                "choices": ["WHERE", "HAVING", "ORDER BY", "LIMIT"],
                "correct_choice_index": 1,
                "explanation": "HAVING filters groups.",
                "source": {"page": 9, "quote": SOURCE},
            } for number in ([1] if retry else [1, 2, 3])]}
        return SimpleNamespace(text=json.dumps(result))

    model = SimpleNamespace(
        count_tokens=lambda **_: SimpleNamespace(total_tokens=200),
        generate_content=generate_content,
    )
    monkeypatch.setattr("app.domains.study.generation.get_gemini_client", lambda: SimpleNamespace(models=model))
    return calls


def prepare(client):
    document_id = upload_pdf(client, study_pdf())["id"]
    path = f"/documents/{document_id}/study"
    assert client.get(path).json()["status"] == "not_prepared"
    response = client.post(f"{path}/prepare")
    assert response.status_code == 200, response.text
    outline = response.json()
    assert outline["status"] == "ready"
    assert [(s["start_page"], s["end_page"]) for s in outline["sections"]] == [(1, 8), (9, 10)]
    assert client.post(f"{path}/prepare").json() == outline
    section = outline["sections"][-1]
    response = client.post(f"/study/sections/{section['id']}/prepare")
    assert response.status_code == 200, response.text
    return path, outline, section, response.json()["parts"][0]["id"]


def test_guided_learning_retry_and_dashboard(workspace, gemini):
    client, _ = workspace
    path, outline, section, part_id = prepare(client)
    assert not gemini
    part_path = f"/study/parts/{part_id}"
    stranger = {"X-Test-User": "2"}
    assert client.get(path, headers=stranger).status_code == 404
    assert client.get(part_path, headers=stranger).status_code == 404
    assert client.post(f"{part_path}/practice", json={"retry": False}).status_code == 409

    lesson = client.post(f"{part_path}/lesson")
    assert lesson.status_code == 200, lesson.text
    assert "[Page 9]" in gemini[-1] and "[Page 10]" in gemini[-1] and "[Page 1]" not in gemini[-1]
    assert client.post(f"{part_path}/lesson").json() == lesson.json()
    assert len(gemini) == 1
    quiz_response = client.post(f"{part_path}/practice", json={"retry": False})
    assert quiz_response.status_code == 200, quiz_response.text
    quiz = quiz_response.json()["quiz"]
    assert len(quiz["questions"]) == 3
    assert set(quiz["questions"][0]) == {"question", "choices"}
    assert quiz_response.json()["feedback"] is None
    submit_path = f"/study/quizzes/{quiz['id']}/submit"
    answers = [{"question_index": index, "selected_choice_index": choice} for index, choice in enumerate([0, 1, 1])]
    assert client.post(submit_path, json={"answers": answers[:2]}).status_code == 422
    assert client.post(submit_path, json={"answers": answers}, headers=stranger).status_code == 404
    graded = client.post(submit_path, json={"answers": answers})
    assert graded.status_code == 200, graded.text
    feedback = graded.json()
    assert feedback["correct_answers"] == 2 and feedback["needs_review"]
    assert feedback["answers"][0]["source"] == {"page": 9, "quote": SOURCE}
    assert client.post(submit_path, json={"answers": list(reversed(answers))}).json() == feedback
    assert client.get(part_path).json()["state"] == "needs_review"
    assert client.get(part_path).json()["feedback"] == feedback

    patch = [{key: s[key] for key in ("id", "title", "start_page", "end_page")} for s in outline["sections"]]
    patch[0]["end_page"] = 7
    patch[-1]["start_page"] = 8
    assert client.patch(f"{path}/sections", json={"sections": patch}).status_code == 409
    patch[0]["end_page"] = 8
    patch[-1].update({"start_page": 9, "title": "Grouping and filters"})
    renamed = client.patch(f"{path}/sections", json={"sections": patch})
    assert renamed.json()["sections"][-1]["title"] == "Grouping and filters"

    pre_retry = client.get("/analytics/study").json()
    assert pre_retry["next_action"]["kind"] == "review"
    assert pre_retry["next_action"]["section_id"] == section["id"]
    retry = client.post(f"{part_path}/practice", json={"retry": True}).json()["quiz"]
    assert retry["id"] != quiz["id"] and retry["kind"] == "retry"
    assert len(retry["questions"]) == 1
    assert retry["questions"][0]["question"] != quiz["questions"][0]["question"]
    assert client.get("/analytics/study").json()["next_action"]["kind"] == "resume"
    retry_result = client.post(f"/study/quizzes/{retry['id']}/submit", json={"answers": [answers[1] | {"question_index": 0}]})
    assert retry_result.status_code == 200, retry_result.text
    assert not retry_result.json()["needs_review"]
    data = client.get("/analytics/study?timezone=Asia%2FBangkok").json()
    assert data["documents"][0]["practiced"] == 1
    assert len(data["daily_attempts"]) == 7
    assert sum(day["initial"] for day in data["daily_attempts"]) == 1
    assert sum(day["retry"] for day in data["daily_attempts"]) == 1
    assert len(data["scores"]) == 1 and len(data["recent_attempts"]) == 2
    assert client.get("/analytics/study", headers=stranger).json()["scores"] == []
    assert client.get("/quizzes/attempts").json() == []


def test_rejects_invented_source_and_preserves_outline(workspace, gemini, monkeypatch):
    client, _ = workspace
    path, outline, _, part_id = prepare(client)
    fake_lesson = {
        "objectives": ["Rows", "Groups", "Totals"],
        "explanation": "Filters",
        "example": "Use a query",
        "sources": [{"page": 1, "quote": SOURCE}],
    }
    model = SimpleNamespace(generate_content=lambda **_: SimpleNamespace(text=json.dumps(fake_lesson)))
    monkeypatch.setattr("app.domains.study.generation.get_gemini_client", lambda: SimpleNamespace(models=model))
    assert client.post(f"/study/parts/{part_id}/lesson").status_code == 502
    assert client.get(f"/study/parts/{part_id}").json()["lesson"] is None
    assert len(client.get(path).json()["sections"]) == len(outline["sections"])


def test_oversized_part_is_split_without_skipping_text(monkeypatch):
    from app.domains.study.generation import split_source

    def count_tokens(**kwargs):
        return SimpleNamespace(total_tokens=len(kwargs["contents"]))

    monkeypatch.setattr(
        "app.domains.study.generation.get_gemini_client",
        lambda: SimpleNamespace(models=SimpleNamespace(count_tokens=count_tokens)),
    )
    page = {"page": 2, "text": "Early." * 800 + "\n\n" + "Late." * 800}
    parts = split_source([page])
    assert len(parts) == 2
    assert all(item["page"] == 2 for part in parts for item in part)
    assert "".join(item["text"] for part in parts for item in part) == page["text"]


def test_dashboard_only_recommends_readable_sections(workspace):
    client, _ = workspace
    blank_id = upload_pdf(client, _pdf([""] * 9))["id"]
    blank = client.post(f"/documents/{blank_id}/study/prepare").json()
    assert blank["status"] == "no_text"
    assert client.get("/analytics/study").json()["next_action"] is None

    document_id = upload_pdf(client, _pdf([""] * 8 + [SOURCE]))["id"]
    outline = client.post(f"/documents/{document_id}/study/prepare").json()
    assert outline["unreadable_pages"] == list(range(1, 9))
    progress = client.get("/analytics/study").json()
    assert progress["next_action"]["section_id"] == outline["sections"][1]["id"]
    assert progress["documents"] == [{
        "id": document_id, "title": "notes.pdf", "not_started": 1,
        "in_progress": 0, "needs_review": 0, "practiced": 0,
    }]


def test_sqlite_cascades_study_data_before_a_document_id_can_be_reused():
    from sqlalchemy.orm import Session

    from app.core.database import Base, create_database_engine
    from app.domains.documents.model import Document
    from app.domains.study.model import StudyIndex, StudySection
    from app.domains.users.model import User

    engine = create_database_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([
            User(id=user_id, email=f"student{user_id}@example.com", full_name="Student", hashed_password="demo")
            for user_id in (1, 2)
        ])
        db.commit()
        document = Document(id=1, owner_id=1, original_filename="Student's PDF", stored_filename="owned.pdf")
        db.add(document)
        db.commit()
        db.add(StudyIndex(document_id=1, status="ready", page_count=1, unreadable_pages=[], pages=[]))
        db.commit()
        db.add(StudySection(id=1, document_id=1, title="Private section", start_page=1, end_page=1))
        db.commit()
        db.delete(document)
        db.commit()
        db.add(Document(id=1, owner_id=2, original_filename="Other PDF", stored_filename="other.pdf"))
        db.commit()
        assert db.get(StudyIndex, 1) is None
        assert db.get(StudySection, 1) is None
    engine.dispose()


def test_sqlite_serializes_guided_writes(tmp_path):
    from sqlalchemy.exc import OperationalError
    from sqlalchemy.orm import Session

    from app.core.database import Base, create_database_engine
    from app.domains.documents.model import Document
    from app.domains.study.service import _owned_document
    from app.domains.users.model import User

    engine = create_database_engine("sqlite:///" + (tmp_path / "concurrent.db").as_posix(),
                                    connect_args={"timeout": 0.05})
    Base.metadata.create_all(engine)
    with Session(engine) as first, Session(engine) as second:
        first.add(User(id=1, email="student@example.com", full_name="Student", hashed_password="demo"))
        first.flush()
        first.add(Document(id=1, owner_id=1, original_filename="PDF", stored_filename="notes.pdf"))
        first.commit()
        _owned_document(first, 1, 1, lock=True)
        with pytest.raises(OperationalError, match="locked"):
            _owned_document(second, 1, 1, lock=True)
        first.rollback()
        second.rollback()
        assert _owned_document(second, 1, 1, lock=True).id == 1
    engine.dispose()


def test_sqlite_outline_reads_from_the_same_snapshot_as_ownership(tmp_path, monkeypatch):
    from sqlalchemy.orm import Session

    from app.core.database import Base, create_database_engine
    from app.domains.documents.model import Document
    from app.domains.study import service
    from app.domains.study.model import StudyIndex, StudySection
    from app.domains.users.model import User

    engine = create_database_engine(f"sqlite:///{(tmp_path / 'outline.db').as_posix()}")
    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA journal_mode=WAL")
    Base.metadata.create_all(engine)

    def seed_outline(db, owner_id, title):
        db.add(Document(id=1, owner_id=owner_id, original_filename=title, stored_filename=title))
        db.flush()
        db.add(StudyIndex(document_id=1, status="ready", page_count=1, unreadable_pages=[], pages=[]))
        db.flush()
        db.add(StudySection(id=1, document_id=1, title=title, start_page=1, end_page=1))
        db.commit()

    original_check = service._owned_document

    def replace_outline_after_check(db, *args, **kwargs):
        document = original_check(db, *args, **kwargs)
        with Session(engine) as writer:
            writer.delete(writer.get(Document, document.id))
            writer.commit()
            seed_outline(writer, 2, "Second user's outline")
        return document

    with Session(engine) as reader:
        reader.add_all([
            User(id=user_id, email=f"student{user_id}@example.com", full_name="Student", hashed_password="demo")
            for user_id in (1, 2)
        ])
        reader.flush()
        seed_outline(reader, 1, "First user's outline")
        monkeypatch.setattr(service, "_owned_document", replace_outline_after_check)
        outline = service.read_outline(reader, 1, 1)
        assert [section.title for section in outline.sections] == ["First user's outline"]
    engine.dispose()
