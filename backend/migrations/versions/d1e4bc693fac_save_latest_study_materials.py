"""Save the latest study materials alongside each document."""

from alembic import op
import sqlalchemy as sa

revision = "d1e4bc693fac"
down_revision = "9ef681b1e85c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("summary_material", sa.JSON(), nullable=True))
    op.add_column("documents", sa.Column("flashcard_material", sa.JSON(), nullable=True))
    op.add_column("documents", sa.Column("roadmap_material", sa.JSON(), nullable=True))
    op.add_column("quizzes", sa.Column("provider", sa.String(32), nullable=True))


def downgrade() -> None:
    op.drop_column("quizzes", "provider")
    op.drop_column("documents", "roadmap_material")
    op.drop_column("documents", "flashcard_material")
    op.drop_column("documents", "summary_material")
