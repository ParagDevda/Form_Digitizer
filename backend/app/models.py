"""Persistent form template models."""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
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
    samples: Mapped[list["TemplateSample"]] = relationship(back_populates="template", cascade="all, delete-orphan")


class TemplateSample(Base):
    __tablename__ = "template_page_samples"

    template_id: Mapped[str] = mapped_column(ForeignKey("form_templates.id", ondelete="CASCADE"), primary_key=True)
    page_number: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    stored_path: Mapped[str] = mapped_column(Text, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(260), nullable=False)
    template: Mapped[FormTemplate] = relationship(back_populates="samples")


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


class Batch(Base):
    __tablename__ = "batches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    batch_name: Mapped[str] = mapped_column(String(160), nullable=False)
    template_id: Mapped[str] = mapped_column(ForeignKey("form_templates.id"), index=True)
    total_documents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    processed_documents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_documents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    documents: Mapped[list["Document"]] = relationship(back_populates="batch", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    batch_id: Mapped[str] = mapped_column(ForeignKey("batches.id", ondelete="CASCADE"), index=True)
    original_filename: Mapped[str] = mapped_column(String(260), nullable=False)
    stored_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="uploaded", index=True, nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False)
    batch: Mapped[Batch] = relationship(back_populates="documents")
    record: Mapped["StudentRecord | None"] = relationship(back_populates="document", cascade="all, delete-orphan", uselist=False)


class StudentRecord(Base):
    __tablename__ = "student_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), unique=True, index=True)
    template_id: Mapped[str] = mapped_column(ForeignKey("form_templates.id"), index=True)
    student_identifier: Mapped[str | None] = mapped_column(String(160), nullable=True)
    student_name: Mapped[str | None] = mapped_column(String(250), nullable=True)
    verification_status: Mapped[str] = mapped_column(String(24), default="pending", index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False)
    document: Mapped[Document] = relationship(back_populates="record")
    answers: Mapped[list["Answer"]] = relationship(back_populates="record", cascade="all, delete-orphan")


class Answer(Base):
    __tablename__ = "answers"
    __table_args__ = (UniqueConstraint("student_record_id", "question_id", name="uq_record_question"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    student_record_id: Mapped[str] = mapped_column(ForeignKey("student_records.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), index=True)
    page_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    raw_ocr_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    normalized_ocr_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    corrected_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    verification_status: Mapped[str] = mapped_column(String(24), default="needs_review", index=True, nullable=False)
    ocr_model: Mapped[str | None] = mapped_column(String(160), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False)

    record: Mapped[StudentRecord] = relationship(back_populates="answers")
