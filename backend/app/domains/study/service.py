import logging
from dataclasses import dataclass, field
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, undefer

from app.core.database import begin_sqlite_transaction
from app.domains.documents.dependencies import get_original_pdf
from app.domains.documents.model import Document
from app.domains.documents.pdf_text import PDFExtractionBusy, PDFExtractionError, index_pdf_for_study
from app.domains.quizzes.service import calculate_score_percentage, grade_saved_quiz
from app.domains.study import generation
from app.domains.study.model import StudyAttempt, StudyIndex, StudyPart, StudyQuiz, StudySection
from app.domains.study.schemas import (
    Feedback, Outline, OutlineEdit, PartRead, PartSummary, QuizRead, QuizSubmission,
    SectionRead, State,
)


logger = logging.getLogger(__name__)


@dataclass
class PartProgress:
    part: StudyPart
    has_lesson: bool
    quiz_id: int | None = None
    pending: bool = False
    activity_at: datetime | None = None
    outcomes: dict[int, bool] = field(default_factory=dict)

    @property
    def missed(self) -> set[int]:
        return {topic_id for topic_id, correct in self.outcomes.items() if not correct}

    @property
    def state(self) -> State:
        if self.missed:
            return "needs_review"
        if len(self.outcomes) == 3:
            return "practiced"
        if self.has_lesson or self.quiz_id is not None:
            return "in_progress"
        return "not_started"


def _owned_document(db: Session, document_id: int, owner_id: int, *, lock=False) -> Document:
    begin_sqlite_transaction(db, write=lock)
    query = select(Document).where(Document.id == document_id, Document.owner_id == owner_id)
    if lock and db.get_bind().dialect.name != "sqlite":
        query = query.with_for_update()
    document = db.scalar(query)
    if document is None:
        raise HTTPException(404, "Document not found.")
    return document


def _owned_section(db: Session, section_id: int, owner_id: int) -> StudySection:
    begin_sqlite_transaction(db)
    section = db.scalar(select(StudySection).join(
        Document, StudySection.document_id == Document.id,
    ).where(StudySection.id == section_id, Document.owner_id == owner_id))
    if section is None:
        raise HTTPException(404, "Study section not found.")
    return section


def _owned_part(db: Session, part_id: int, owner_id: int) -> tuple[StudyPart, StudySection]:
    begin_sqlite_transaction(db)
    row = db.execute(select(StudyPart, StudySection).options(undefer(StudyPart.lesson)).join(StudySection).join(
        Document, StudySection.document_id == Document.id,
    ).where(StudyPart.id == part_id, Document.owner_id == owner_id)).one_or_none()
    if row is None:
        raise HTTPException(404, "Study part not found.")
    return tuple(row)


def _sections(db: Session, document_id: int) -> list[StudySection]:
    return list(db.scalars(
        select(StudySection).where(StudySection.document_id == document_id).order_by(StudySection.start_page)
    ))


def section_progress(db: Session, section_ids: list[int]) -> dict[int, list[PartProgress]]:
    grouped = {section_id: [] for section_id in section_ids}
    if not section_ids:
        return grouped
    parts = {}
    for part, has_lesson in db.execute(select(StudyPart, StudyPart.lesson.is_not(None)).where(
        StudyPart.section_id.in_(section_ids)
    ).order_by(StudyPart.number)):
        parts[part.id] = PartProgress(part, has_lesson)
        grouped[part.section_id].append(parts[part.id])
    _apply_quiz_history(db, parts)
    return grouped


def _apply_quiz_history(db: Session, parts: dict[int, PartProgress], up_to_quiz_id: int | None = None) -> None:
    if not parts:
        return
    query = (
        select(StudyQuiz.part_id, StudyQuiz.id, StudyQuiz.created_at, StudyQuiz.questions,
               StudyAttempt.answers, StudyAttempt.created_at)
        .outerjoin(StudyAttempt)
        .where(StudyQuiz.part_id.in_(parts))
        .order_by(StudyQuiz.id.desc())
    )
    if up_to_quiz_id is not None:
        query = query.where(StudyQuiz.id <= up_to_quiz_id)
    for part_id, *history in db.execute(query).yield_per(100):
        _record_progress(parts[part_id], *history)


def _record_progress(progress, quiz_id, created_at, questions, answers, submitted_at) -> None:
    if progress.quiz_id is None:
        progress.quiz_id = quiz_id
        progress.pending = answers is None
        progress.activity_at = submitted_at or created_at
    if answers is not None and len(progress.outcomes) < 3:
        for question, selected in zip(questions, answers, strict=True):
            progress.outcomes.setdefault(question["topic_id"], selected == question["correct_choice_index"])


def _part_progress(db: Session, part: StudyPart, *, up_to_quiz_id: int | None = None) -> PartProgress:
    progress = PartProgress(part, part.lesson is not None)
    _apply_quiz_history(db, {part.id: progress}, up_to_quiz_id)
    return progress


def section_state(parts: list[PartProgress]) -> State:
    states = {part.state for part in parts}
    if "needs_review" in states:
        return "needs_review"
    if states == {"practiced"}:
        return "practiced"
    if "in_progress" in states or "practiced" in states:
        return "in_progress"
    return "not_started"


def _part_summary(progress: PartProgress) -> PartSummary:
    part = progress.part
    return PartSummary(
        id=part.id, number=part.number, start_page=part.start_page, end_page=part.end_page, state=progress.state,
    )


def _section_view(section: StudySection, parts: list[PartProgress]) -> SectionRead:
    return SectionRead(
        id=section.id, title=section.title, start_page=section.start_page, end_page=section.end_page,
        state=section_state(parts), locked=any(part.quiz_id is not None for part in parts),
        parts=[_part_summary(part) for part in parts],
    )


def read_outline(db: Session, document_id: int, owner_id: int) -> Outline:
    _owned_document(db, document_id, owner_id)
    index = db.get(StudyIndex, document_id)
    if index is None:
        return Outline(document_id=document_id, status="not_prepared", reason=None,
                       page_count=0, unreadable_pages=[], sections=[])
    sections = _sections(db, document_id)
    progress = section_progress(db, [section.id for section in sections])
    return Outline(
        document_id=document_id, status=index.status, reason=index.reason, page_count=index.page_count,
        unreadable_pages=index.unreadable_pages,
        sections=[_section_view(section, progress[section.id]) for section in sections],
    )


def prepare_outline(db: Session, document_id: int, owner_id: int) -> Outline:
    document = _owned_document(db, document_id, owner_id)
    if db.get(StudyIndex, document_id) is not None:
        return read_outline(db, document_id, owner_id)

    # Release the read transaction while storage and the bounded worker run.
    db.expunge(document)
    db.rollback()
    try:
        result = index_pdf_for_study(get_original_pdf(document))
    except PDFExtractionBusy:
        raise HTTPException(503, "PDF preparation is busy. Try again shortly.") from None
    except PDFExtractionError:
        logger.warning("Guided PDF preparation failed for document %d", document_id)
        raise HTTPException(422, "We couldn't read this PDF. Try again or upload another copy.") from None
    if result["status"] != "ready":
        logger.info("Guided PDF preparation ended with %s for document %d", result["status"], document_id)

    _owned_document(db, document_id, owner_id, lock=True)
    if db.get(StudyIndex, document_id) is None:
        db.add(StudyIndex(
            document_id=document_id, status=result["status"], reason=result["reason"],
            page_count=result["page_count"], unreadable_pages=result["unreadable_pages"], pages=result["pages"],
        ))
        db.flush()
        if result["status"] == "ready":
            db.add_all([StudySection(document_id=document_id, **section) for section in result["sections"]])
        db.commit()
    return read_outline(db, document_id, owner_id)


def edit_outline(db: Session, document_id: int, owner_id: int, edit: OutlineEdit) -> Outline:
    _owned_document(db, document_id, owner_id, lock=True)
    index = db.get(StudyIndex, document_id)
    if index is None or index.status != "ready":
        raise HTTPException(409, "Prepare this PDF before editing its sections.")
    sections = {section.id: section for section in _sections(db, document_id)}
    progress = section_progress(db, list(sections))
    retained = {}
    cursor = 1
    for item in edit.sections:
        if item.start_page != cursor or not item.start_page <= item.end_page <= index.page_count:
            raise HTTPException(422, "Sections must cover every page in order without gaps or overlap.")
        cursor = item.end_page + 1
        if item.id is not None:
            if item.id not in sections or item.id in retained:
                raise HTTPException(422, "Invalid section in the outline.")
            retained[item.id] = item
    if cursor != index.page_count + 1:
        raise HTTPException(422, "Sections must cover every page in order without gaps or overlap.")

    for section_id, section in sections.items():
        item = retained.get(section_id)
        changed = item is None or (item.start_page, item.end_page) != (section.start_page, section.end_page)
        if changed and any(part.quiz_id is not None for part in progress[section_id]):
            raise HTTPException(409, "You can rename a practiced section, but its page range is locked.")
        if item is None:
            db.delete(section)
        else:
            if changed:
                for data in progress[section_id]:
                    db.delete(data.part)
            section.title, section.start_page, section.end_page = item.title, item.start_page, item.end_page
    for item in edit.sections:
        if item.id is None:
            db.add(StudySection(document_id=document_id, **item.model_dump(exclude={"id"})))
    db.commit()
    return read_outline(db, document_id, owner_id)


def prepare_section(db: Session, section_id: int, owner_id: int) -> SectionRead:
    section = _owned_section(db, section_id, owner_id)
    existing = section_progress(db, [section_id])[section_id]
    if existing:
        return _section_view(section, existing)
    document_id = section.document_id
    bounds = section.start_page, section.end_page
    index = db.get(StudyIndex, document_id)
    pages = [page for page in index.pages if bounds[0] <= page["page"] <= bounds[1]]
    db.rollback()
    try:
        sources = generation.split_source(pages)
    except generation.StudySourceTooLarge:
        raise HTTPException(422, "This section is too large to prepare at once. Choose smaller page ranges.") from None
    if not sources:
        raise HTTPException(422, "There is no selectable text in this section. Try another page range.")

    _owned_document(db, document_id, owner_id, lock=True)
    section = _owned_section(db, section_id, owner_id)
    if (section.start_page, section.end_page) != bounds:
        raise HTTPException(409, "The section changed during preparation. Open it again.")
    if not section_progress(db, [section_id])[section_id]:
        db.add_all([
            StudyPart(section_id=section_id, number=number, start_page=source[0]["page"],
                      end_page=source[-1]["page"], source=source)
            for number, source in enumerate(sources, start=1)
        ])
        db.commit()
        section = _owned_section(db, section_id, owner_id)
    return _section_view(section, section_progress(db, [section_id])[section_id])


def _feedback(quiz: StudyQuiz, attempt: StudyAttempt, lesson: dict, needs_review: bool) -> Feedback:
    topics = {item["id"]: item["title"] for item in lesson["objectives"]}
    return Feedback(
        quiz_id=quiz.id, kind=quiz.kind, correct_answers=attempt.correct_answers,
        total_questions=attempt.total_questions, needs_review=needs_review,
        score_percentage=calculate_score_percentage(attempt.correct_answers, attempt.total_questions),
        answers=[
            {
                "question": question["question"], "choices": question["choices"],
                "topic": topics[question["topic_id"]], "selected_choice_index": selected,
                "correct_choice_index": question["correct_choice_index"],
                "correct": selected == question["correct_choice_index"],
                "explanation": question["explanation"], "source": question["source"],
            }
            for question, selected in zip(quiz.questions, attempt.answers, strict=True)
        ],
    )


def read_part(db: Session, part_id: int, owner_id: int) -> PartRead:
    part, section = _owned_part(db, part_id, owner_id)
    progress = PartProgress(part, part.lesson is not None)
    latest = submitted = None
    # Read the quiz, submitted feedback, and progress from one statement snapshot.
    for quiz, attempt in db.execute(
        select(StudyQuiz, StudyAttempt).options(undefer(StudyQuiz.questions)).outerjoin(StudyAttempt)
        .where(StudyQuiz.part_id == part_id).order_by(StudyQuiz.id.desc())
    ).yield_per(20):
        if latest is None:
            latest = quiz
        if attempt is not None and submitted is None:
            submitted = (quiz, attempt)
        _record_progress(progress, quiz.id, quiz.created_at, quiz.questions,
                         attempt.answers if attempt else None, attempt.created_at if attempt else None)
        if len(progress.outcomes) == 3:
            break
    result = _feedback(*submitted, part.lesson, needs_review=bool(progress.missed)) if submitted else None
    return PartRead(
        **_part_summary(progress).model_dump(), section_id=section.id, document_id=section.document_id,
        lesson=part.lesson, feedback=result,
        quiz=QuizRead(id=latest.id, kind=latest.kind, questions=latest.questions) if latest else None,
    )


def _lock_unchanged_part(db: Session, part_id: int, document_id: int, owner_id: int, source: list) -> StudyPart:
    _owned_document(db, document_id, owner_id, lock=True)
    part, _ = _owned_part(db, part_id, owner_id)
    if part.source != source:
        raise HTTPException(409, "The section changed while this material was generated. Open it again.")
    return part


def prepare_lesson(db: Session, part_id: int, owner_id: int) -> PartRead:
    part, section = _owned_part(db, part_id, owner_id)
    if part.lesson is None:
        source, document_id = part.source, section.document_id
        db.rollback()
        lesson = generation.generate_lesson(source)
        part = _lock_unchanged_part(db, part_id, document_id, owner_id, source)
        if part.lesson is None:
            part.lesson = lesson
            db.commit()
    return read_part(db, part_id, owner_id)


def prepare_practice(db: Session, part_id: int, owner_id: int, retry: bool) -> PartRead:
    part, section = _owned_part(db, part_id, owner_id)
    if part.lesson is None:
        raise HTTPException(409, "Generate the lesson before starting practice.")
    progress = _part_progress(db, part)
    if progress.pending or (not retry and progress.quiz_id is not None):
        return read_part(db, part_id, owner_id)

    objectives = part.lesson["objectives"]
    previous_questions = []
    kind = "initial"
    if retry:
        if not progress.missed:
            raise HTTPException(409, "There are no missed concepts to retry.")
        kind = "retry"
        objectives = [objective for objective in objectives if objective["id"] in progress.missed]
        previous_questions = [
            item["question"]
            for questions in db.scalars(select(StudyQuiz.questions).where(
                StudyQuiz.part_id == part_id,
            ).order_by(StudyQuiz.id.desc()))
            for item in questions
        ]
    source, document_id = part.source, section.document_id
    db.rollback()
    questions = generation.generate_practice(source, objectives, previous_questions)
    part = _lock_unchanged_part(db, part_id, document_id, owner_id, source)
    if _part_progress(db, part).quiz_id == progress.quiz_id:
        db.add(StudyQuiz(part_id=part_id, kind=kind, questions=questions))
        db.commit()
    return read_part(db, part_id, owner_id)


def submit_practice(db: Session, quiz_id: int, owner_id: int, submission: QuizSubmission) -> Feedback:
    row = db.execute(
        select(StudyQuiz.part_id, StudySection.document_id).select_from(StudyQuiz)
        .join(StudyPart, StudyQuiz.part_id == StudyPart.id)
        .join(StudySection, StudyPart.section_id == StudySection.id)
        .join(Document, StudySection.document_id == Document.id)
        .where(StudyQuiz.id == quiz_id, Document.owner_id == owner_id)
    ).one_or_none()
    if row is None:
        raise HTTPException(404, "Study quiz not found.")
    part_id, document_id = row
    db.rollback()
    _owned_document(db, document_id, owner_id, lock=True)
    part, _ = _owned_part(db, part_id, owner_id)
    quiz = db.scalar(select(StudyQuiz).where(StudyQuiz.id == quiz_id, StudyQuiz.part_id == part.id))
    if quiz is None:
        raise HTTPException(404, "Study quiz not found.")
    if len(submission.answers) != len(quiz.questions):
        raise HTTPException(422, "Answer every question exactly once.")
    try:
        correct = grade_saved_quiz(quiz.questions, submission.answers)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    answers = [item.selected_choice_index for item in sorted(submission.answers, key=lambda item: item.question_index)]
    attempt = db.scalar(select(StudyAttempt).where(StudyAttempt.quiz_id == quiz_id))
    if attempt is not None and attempt.answers != answers:
        raise HTTPException(409, "This quiz has already been submitted.")
    if attempt is None:
        attempt = StudyAttempt(quiz_id=quiz_id, answers=answers, correct_answers=correct, total_questions=len(answers))
        db.add(attempt)
        db.flush()
    progress = _part_progress(db, part, up_to_quiz_id=quiz_id)
    result = _feedback(quiz, attempt, part.lesson, needs_review=bool(progress.missed))
    db.commit()
    return result
