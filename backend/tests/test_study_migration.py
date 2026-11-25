from datetime import datetime, timezone
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings


PREVIOUS_HEAD = "d1e4bc693fac"
STUDY_TABLES = {
    "study_indexes",
    "study_sections",
    "study_parts",
    "study_quizzes",
    "study_attempts",
}


def test_study_migration_round_trip(tmp_path, monkeypatch):
    backend = Path(__file__).resolve().parents[1]
    config = Config(str(backend / "alembic.ini"))
    url = sa.URL.create("sqlite", database=str(tmp_path / "study.db"))
    monkeypatch.setattr(settings, "database_url", url.render_as_string())
    engine = sa.create_engine(url)

    try:
        command.upgrade(config, PREVIOUS_HEAD)
        original_tables = set(sa.inspect(engine).get_table_names())
        command.upgrade(config, "head")
        inspector = sa.inspect(engine)
        assert set(inspector.get_table_names()) == original_tables | STUDY_TABLES
        for table, column in (
            ("study_sections", "document_id"),
            ("study_parts", "section_id"),
            ("study_quizzes", "part_id"),
            ("study_attempts", "created_at"),
        ):
            assert [column] in [index["column_names"] for index in inspector.get_indexes(table)]

        from app.domains.study.model import (
            StudyAttempt,
            StudyIndex,
            StudyPart,
            StudyQuiz,
            StudySection,
        )

        metadata = sa.MetaData()
        users = sa.Table("users", metadata, autoload_with=engine)
        documents = sa.Table("documents", metadata, autoload_with=engine)
        with engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            connection.commit()
            with Session(connection) as session:
                session.execute(users.insert().values(
                    id=1, email="test@example.com", full_name="Test User",
                    hashed_password="unused", is_active=True, role="student",
                ))
                now = datetime.now(timezone.utc)
                session.execute(documents.insert().values(
                    id=1, owner_id=1, original_filename="test.pdf",
                    stored_filename="test.pdf", processing_status="uploaded",
                    created_at=now, updated_at=now,
                ))
                session.add(StudyIndex(
                    document_id=1, status="ready", page_count=1,
                    unreadable_pages=[], pages=[{"page": 1}],
                ))
                session.flush()
                session.add(StudySection(
                    id=1, document_id=1, title="Intro", start_page=1, end_page=1,
                ))
                session.flush()
                session.add(StudyPart(
                    id=1, section_id=1, number=1, start_page=1, end_page=1,
                    source=[{"page": 1}],
                ))
                session.flush()
                session.add(StudyQuiz(id=1, part_id=1, kind="initial", questions=[{}]))
                session.flush()
                session.add(StudyAttempt(
                    id=1, quiz_id=1, answers=[0], correct_answers=1, total_questions=1,
                ))
                session.commit()
                session.expunge_all()

                study_index = session.get(StudyIndex, 1)
                study_part = session.get(StudyPart, 1)
                study_quiz = session.get(StudyQuiz, 1)
                assert "pages" in sa.inspect(study_index).unloaded
                assert {"source", "lesson"} <= sa.inspect(study_part).unloaded
                assert "questions" in sa.inspect(study_quiz).unloaded
                assert study_index.pages == [{"page": 1}]
                assert study_part.lesson is None
                assert session.get(StudyAttempt, 1).answers == [0]

                for model in (
                    StudyPart(
                        section_id=1, number=1, start_page=1, end_page=1, source=[],
                    ),
                    StudyPart(
                        section_id=1, number=0, start_page=1, end_page=1, source=[],
                    ),
                    StudyQuiz(part_id=1, kind="unknown", questions=[]),
                    StudyAttempt(
                        quiz_id=1, answers=[0], correct_answers=1, total_questions=1,
                    ),
                ):
                    with pytest.raises(IntegrityError), session.begin_nested():
                        session.add(model)
                        session.flush()

                session.execute(documents.delete().where(documents.c.id == 1))
                for model in (StudyIndex, StudySection, StudyPart, StudyQuiz, StudyAttempt):
                    count = session.scalar(sa.select(sa.func.count()).select_from(model))
                    assert count == 0
                session.commit()

        command.downgrade(config, PREVIOUS_HEAD)
        assert set(sa.inspect(engine).get_table_names()) == original_tables
        with engine.connect() as connection:
            assert connection.scalar(sa.select(users.c.id)) == 1
        command.upgrade(config, "head")
        assert set(sa.inspect(engine).get_table_names()) == original_tables | STUDY_TABLES
    finally:
        engine.dispose()
