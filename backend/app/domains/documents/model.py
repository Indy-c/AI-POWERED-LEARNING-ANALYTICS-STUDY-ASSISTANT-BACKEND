from datetime import datetime, timezone

from sqlalchemy import String, DateTime, ForeignKey, JSON, Text, false, func
from sqlalchemy.orm import Mapped, column_property, mapped_column

from app.core.database import Base

# Database table for uploaded study materials (documents)
class Document(Base):
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(255), nullable=False)    
    file_path: Mapped[str] = mapped_column(Text, nullable=True)
    content_type: Mapped[str] = mapped_column(String(100), default="application/pdf", nullable=True)
    processing_status: Mapped[str] = mapped_column(String(50), default="uploaded", nullable=False)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True, deferred=True)
    has_extracted_text: Mapped[bool] = column_property(func.coalesce(func.length(extracted_text) > 0, false()))
    summary_material: Mapped[dict | None] = mapped_column(JSON, deferred=True, deferred_group="study_materials")
    flashcard_material: Mapped[dict | None] = mapped_column(JSON, deferred=True, deferred_group="study_materials")
    roadmap_material: Mapped[dict | None] = mapped_column(JSON, deferred=True, deferred_group="study_materials")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
