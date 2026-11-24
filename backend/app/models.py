"""Persistent form template models."""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class FormTemplate(Base):
    __tablename__ = "form_templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    version: Mapped[str] = mapped_column(String(40), default="1.0", nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False)
    questions: Mapped[list["Question"]] = relationship(back_populates="template", cascade="all, delete-orphan", order_by="Question.display_order")


class Question(Base):
    __tablename__ = "questions"
    __table_args__ = (UniqueConstraint("template_id", "question_number", name="uq_question_number_per_template"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    template_id: Mapped[str] = mapped_column(ForeignKey("form_templates.id", ondelete="CASCADE"), index=True)
    question_number: Mapped[int] = mapped_column(Integer, nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    answer_type: Mapped[str] = mapped_column(String(32), default="short_text", nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    region_x: Mapped[float | None] = mapped_column(nullable=True)
    region_y: Mapped[float | None] = mapped_column(nullable=True)
    region_width: Mapped[float | None] = mapped_column(nullable=True)
    region_height: Mapped[float | None] = mapped_column(nullable=True)
    template: Mapped[FormTemplate] = relationship(back_populates="questions")
