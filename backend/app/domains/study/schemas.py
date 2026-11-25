from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints


State = Literal["not_started", "in_progress", "needs_review", "practiced"]
QuizKind = Literal["initial", "retry"]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
BriefText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=650)]
LessonText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]


class SourceRef(BaseModel):
    page: int = Field(ge=1)
    quote: Annotated[str, StringConstraints(strip_whitespace=True, min_length=8, max_length=360)]


class Objective(BaseModel):
    id: int
    title: Title


class LessonDraft(BaseModel):
    objectives: list[Title] = Field(min_length=3, max_length=3)
    explanation: LessonText
    example: LessonText
    sources: list[SourceRef] = Field(min_length=1, max_length=4)


class LessonRead(BaseModel):
    objectives: list[Objective]
    explanation: str
    example: str
    sources: list[SourceRef]


class QuestionDraft(BaseModel):
    question: BriefText
    topic_id: int = Field(ge=1)
    choices: list[BriefText] = Field(min_length=4, max_length=4)
    correct_choice_index: int = Field(ge=0, le=3)
    explanation: BriefText
    source: SourceRef


class QuizDraft(BaseModel):
    questions: list[QuestionDraft] = Field(min_length=1, max_length=3)


class QuestionRead(BaseModel):
    question: str
    choices: list[str]


class QuizRead(BaseModel):
    id: int
    kind: QuizKind
    questions: list[QuestionRead]


class AnswerReview(QuestionRead):
    topic: str
    selected_choice_index: int
    correct_choice_index: int
    correct: bool
    explanation: str
    source: SourceRef


class Feedback(BaseModel):
    quiz_id: int
    kind: QuizKind
    correct_answers: int
    total_questions: int
    score_percentage: float
    needs_review: bool
    answers: list[AnswerReview]


class PartSummary(BaseModel):
    id: int
    number: int
    start_page: int
    end_page: int
    state: State


class PartRead(PartSummary):
    section_id: int
    document_id: int
    lesson: LessonRead | None
    quiz: QuizRead | None
    feedback: Feedback | None


class SectionRead(BaseModel):
    id: int
    title: str
    start_page: int
    end_page: int
    state: State
    locked: bool
    parts: list[PartSummary]


class Outline(BaseModel):
    document_id: int
    status: Literal["not_prepared", "ready", "no_text", "unsupported"]
    reason: str | None
    page_count: int
    unreadable_pages: list[int]
    sections: list[SectionRead]


class SectionEdit(BaseModel):
    id: int | None = Field(default=None, ge=1)
    title: Title
    start_page: int = Field(ge=1)
    end_page: int = Field(ge=1)


class OutlineEdit(BaseModel):
    sections: list[SectionEdit] = Field(min_length=1, max_length=300)


class PracticeRequest(BaseModel):
    retry: bool = False


class ChoiceSubmission(BaseModel):
    question_index: int = Field(ge=0)
    selected_choice_index: int = Field(ge=0, le=3)


class QuizSubmission(BaseModel):
    answers: list[ChoiceSubmission] = Field(min_length=1, max_length=3)


class NextAction(BaseModel):
    kind: Literal["resume", "review", "start"]
    document_id: int
    document_title: str
    section_id: int
    section_title: str
    part_id: int | None


class DocumentProgress(BaseModel):
    id: int
    title: str
    not_started: int = 0
    in_progress: int = 0
    needs_review: int = 0
    practiced: int = 0


class ScorePoint(BaseModel):
    id: int
    document_id: int
    document_title: str
    section_title: str
    part_number: int
    created_at: datetime
    score_percentage: float
    correct_answers: int
    total_questions: int


class RecentAttempt(ScorePoint):
    kind: QuizKind


class DailyAttempts(BaseModel):
    date: str
    initial: int = 0
    retry: int = 0


class StudyAnalytics(BaseModel):
    next_action: NextAction | None
    documents: list[DocumentProgress]
    scores: list[ScorePoint]
    daily_attempts: list[DailyAttempts]
    recent_attempts: list[RecentAttempt]
