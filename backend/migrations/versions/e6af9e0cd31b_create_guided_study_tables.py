"""Create the StudyPilot guided-study tables."""

from alembic import op
import sqlalchemy as sa

revision = "e6af9e0cd31b"
down_revision = "d1e4bc693fac"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "study_indexes",
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("unreadable_pages", sa.JSON(), nullable=False),
        sa.Column("pages", sa.JSON(), nullable=False),
        sa.CheckConstraint("page_count >= 0", name="ck_study_indexes_page_count"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("document_id"),
    )
    op.create_table(
        "study_sections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("start_page", sa.Integer(), nullable=False),
        sa.Column("end_page", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "start_page >= 0 AND end_page >= start_page",
            name="ck_study_sections_page_range",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"], ["study_indexes.document_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_study_sections_document_id"), "study_sections", ["document_id"]
    )
    op.create_table(
        "study_parts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("section_id", sa.Integer(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("start_page", sa.Integer(), nullable=False),
        sa.Column("end_page", sa.Integer(), nullable=False),
        sa.Column("source", sa.JSON(), nullable=False),
        sa.Column("lesson", sa.JSON(none_as_null=True), nullable=True),
        sa.CheckConstraint("number >= 1", name="ck_study_parts_number"),
        sa.CheckConstraint(
            "start_page >= 0 AND end_page >= start_page",
            name="ck_study_parts_page_range",
        ),
        sa.ForeignKeyConstraint(["section_id"], ["study_sections.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("section_id", "number", name="uq_study_parts_section_number"),
    )
    op.create_index(op.f("ix_study_parts_section_id"), "study_parts", ["section_id"])
    op.create_table(
        "study_quizzes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("part_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(7), nullable=False),
        sa.Column("questions", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("kind IN ('initial', 'retry')", name="ck_study_quizzes_kind"),
        sa.ForeignKeyConstraint(["part_id"], ["study_parts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_study_quizzes_part_id"), "study_quizzes", ["part_id"])
    op.create_table(
        "study_attempts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("quiz_id", sa.Integer(), nullable=False),
        sa.Column("answers", sa.JSON(), nullable=False),
        sa.Column("correct_answers", sa.Integer(), nullable=False),
        sa.Column("total_questions", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "correct_answers >= 0 AND total_questions >= correct_answers",
            name="ck_study_attempts_score",
        ),
        sa.ForeignKeyConstraint(["quiz_id"], ["study_quizzes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("quiz_id", name="uq_study_attempts_quiz_id"),
    )
    op.create_index(op.f("ix_study_attempts_created_at"), "study_attempts", ["created_at"])


def downgrade() -> None:
    op.drop_index(op.f("ix_study_attempts_created_at"), table_name="study_attempts")
    op.drop_table("study_attempts")
    op.drop_index(op.f("ix_study_quizzes_part_id"), table_name="study_quizzes")
    op.drop_table("study_quizzes")
    op.drop_index(op.f("ix_study_parts_section_id"), table_name="study_parts")
    op.drop_table("study_parts")
    op.drop_index(op.f("ix_study_sections_document_id"), table_name="study_sections")
    op.drop_table("study_sections")
    op.drop_table("study_indexes")
