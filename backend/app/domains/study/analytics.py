from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import begin_sqlite_transaction
from app.domains.documents.model import Document
from app.domains.quizzes.service import calculate_score_percentage
from app.domains.study.model import StudyAttempt, StudyIndex, StudyPart, StudyQuiz, StudySection
from app.domains.study.schemas import DailyAttempts, DocumentProgress, NextAction, StudyAnalytics
from app.domains.study.service import section_progress, section_state


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _attempts(owner_id: int, document_id: int | None):
    query = (
        select(StudyAttempt, StudyQuiz.kind, StudyPart.number, StudySection.title,
               Document.id, Document.original_filename)
        .join(StudyQuiz, StudyAttempt.quiz_id == StudyQuiz.id)
        .join(StudyPart, StudyQuiz.part_id == StudyPart.id)
        .join(StudySection, StudyPart.section_id == StudySection.id)
        .join(Document, StudySection.document_id == Document.id)
        .where(Document.owner_id == owner_id)
    )
    return query.where(Document.id == document_id) if document_id is not None else query


def _score(row, *, include_kind=False) -> dict:
    attempt, kind, number, section_title, document_id, title = row
    point = {
        "id": attempt.id, "document_id": document_id, "document_title": title,
        "section_title": section_title, "part_number": number, "created_at": _utc(attempt.created_at),
        "correct_answers": attempt.correct_answers, "total_questions": attempt.total_questions,
        "score_percentage": calculate_score_percentage(attempt.correct_answers, attempt.total_questions),
    }
    if include_kind:
        point["kind"] = kind
    return point


def read_analytics(db: Session, owner_id: int, document_id: int | None, timezone: str) -> StudyAnalytics:
    try:
        zone = ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError):
        raise HTTPException(422, "Unknown time zone.") from None
    begin_sqlite_transaction(db)
    if document_id is not None and db.scalar(select(Document.id).where(
        Document.id == document_id, Document.owner_id == owner_id,
    )) is None:
        raise HTTPException(404, "Document not found.")

    sections = [
        (section, title, created_at)
        for section, title, created_at, unreadable in db.execute(
            select(StudySection, Document.original_filename, Document.created_at, StudyIndex.unreadable_pages)
            .join(Document, StudySection.document_id == Document.id)
            .join(StudyIndex, StudySection.document_id == StudyIndex.document_id)
            .where(Document.owner_id == owner_id, StudyIndex.status == "ready")
            .order_by(Document.created_at.desc(), Document.id.desc(), StudySection.start_page)
        )
        if not set(range(section.start_page, section.end_page + 1)).issubset(unreadable)
    ]
    progress = section_progress(db, [section.id for section, *_ in sections])
    documents = {}
    next_candidates = []
    document_activity = {}
    for section, title, created_at in sections:
        doc_id = section.document_id
        totals = documents.setdefault(doc_id, DocumentProgress(id=doc_id, title=title))
        parts = progress[section.id]
        state = section_state(parts)
        setattr(totals, state, getattr(totals, state) + 1)
        document_activity.setdefault(doc_id, _utc(created_at))
        if document_id is not None and doc_id != document_id:
            continue
        for part in parts:
            if part.activity_at is not None:
                document_activity[doc_id] = max(document_activity[doc_id], _utc(part.activity_at))
            if part.pending:
                next_candidates.append((0, _utc(part.activity_at), section, title, part.part.id, "resume"))
            elif part.missed:
                next_candidates.append((1, _utc(part.activity_at), section, title, part.part.id, "review"))
        unfinished = next((item for item in parts if item.state != "practiced"), None)
        if not parts or unfinished is not None:
            part_id = unfinished.part.id if unfinished is not None else None
            next_candidates.append((2, _utc(created_at), section, title, part_id, "start"))

    next_action = None
    if next_candidates:
        _, _, section, title, part_id, kind = min(next_candidates, key=lambda item: (
            item[0],
            -(document_activity[item[2].document_id] if item[0] == 2 else item[1]).timestamp(),
            -item[2].document_id,
            item[2].start_page,
        ))
        next_action = NextAction(
            kind=kind, document_id=section.document_id, document_title=title,
            section_id=section.id, section_title=section.title, part_id=part_id,
        )

    query = _attempts(owner_id, document_id)
    recent = query.order_by(StudyAttempt.created_at.desc(), StudyAttempt.id.desc())
    initial = db.execute(recent.where(StudyQuiz.kind == "initial").limit(20)).all()
    activity = db.execute(recent.limit(12)).all()
    today = datetime.now(zone).date()
    first_day = today - timedelta(days=6)
    daily = {
        day: DailyAttempts(date=day.isoformat())
        for day in (first_day + timedelta(days=offset) for offset in range(7))
    }
    first_instant = datetime.combine(first_day, time.min, tzinfo=zone).astimezone(UTC)
    end_instant = datetime.combine(today + timedelta(days=1), time.min, tzinfo=zone).astimezone(UTC)
    for recorded_at, kind in db.execute(
        query.with_only_columns(StudyAttempt.created_at, StudyQuiz.kind)
        .where(StudyAttempt.created_at >= first_instant, StudyAttempt.created_at < end_instant)
    ).yield_per(100):
        day = daily[_utc(recorded_at).astimezone(zone).date()]
        setattr(day, kind, getattr(day, kind) + 1)
    return StudyAnalytics(
        next_action=next_action, documents=list(documents.values()),
        scores=[_score(row) for row in reversed(initial)], daily_attempts=list(daily.values()),
        recent_attempts=[_score(row, include_kind=True) for row in activity],
    )
