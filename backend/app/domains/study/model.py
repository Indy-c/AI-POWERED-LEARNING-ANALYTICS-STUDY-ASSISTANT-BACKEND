from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class StudyIndex(Base):
    __tablename__ = "study_indexes"
    __table_args__ = (
        CheckConstraint("page_count >= 0", name="ck_study_indexes_page_count"),
    )

    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True
    )
    status: Mapped[str] = mapped_column(String)
    reason: Mapped[str | None] = mapped_column(Text)
    page_count: Mapped[int]
    unreadable_pages: Mapped[list[int]] = mapped_column(JSON)
    pages: Mapped[list[dict]] = mapped_column(JSON, deferred=True)


class StudySection(Base):
    __tablename__ = "study_sections"
    __table_args__ = (
        CheckConstraint(
            "start_page >= 0 AND end_page >= start_page",
            name="ck_study_sections_page_range",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("study_indexes.document_id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(160))
    start_page: Mapped[int]
    end_page: Mapped[int]


class StudyPart(Base):
    __tablename__ = "study_parts"
    __table_args__ = (
        UniqueConstraint("section_id", "number", name="uq_study_parts_section_number"),
        CheckConstraint("number >= 1", name="ck_study_parts_number"),
        CheckConstraint(
            "start_page >= 0 AND end_page >= start_page",
            name="ck_study_parts_page_range",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    section_id: Mapped[int] = mapped_column(
        ForeignKey("study_sections.id", ondelete="CASCADE"), index=True
    )
    number: Mapped[int]
    start_page: Mapped[int]
    end_page: Mapped[int]
    source: Mapped[list[dict]] = mapped_column(JSON, deferred=True)
    lesson: Mapped[dict | None] = mapped_column(JSON(none_as_null=True), deferred=True)


class StudyQuiz(Base):
    __tablename__ = "study_quizzes"
    __table_args__ = (
        CheckConstraint("kind IN ('initial', 'retry')", name="ck_study_quizzes_kind"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    part_id: Mapped[int] = mapped_column(
        ForeignKey("study_parts.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(7))
    questions: Mapped[list[dict]] = mapped_column(JSON, deferred=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class StudyAttempt(Base):
    __tablename__ = "study_attempts"
    __table_args__ = (
        UniqueConstraint("quiz_id", name="uq_study_attempts_quiz_id"),
        CheckConstraint(
            "correct_answers >= 0 AND total_questions >= correct_answers",
            name="ck_study_attempts_score",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    quiz_id: Mapped[int] = mapped_column(
        ForeignKey("study_quizzes.id", ondelete="CASCADE")
    )
    answers: Mapped[list[int]] = mapped_column(JSON)
    correct_answers: Mapped[int]
    total_questions: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )
