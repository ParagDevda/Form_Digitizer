"""Sequential, restart-safe document processing worker."""

import shutil
import threading
from pathlib import Path

import cv2
from sqlalchemy import select

from app.database import PROJECT_ROOT, SessionLocal
from app.models import Answer, Batch, Document, FormTemplate, Question, StudentRecord, TemplateSample
from app.services.image_processing.images import align_to_template, correct_document_perspective, crop_region, load_image, render_pdf
from app.services.ocr.lines import segment_lines
from app.services.ocr.trocr import TrOCRProvider

_provider: TrOCRProvider | None = None
_provider_lock = threading.Lock()


def get_provider() -> TrOCRProvider:
    """Create one lazy CPU provider and reuse it for all queued batches."""
    global _provider
    if _provider is None:
        with _provider_lock:
            if _provider is None:
                _provider = TrOCRProvider()
    return _provider


def refresh_batch_counts(db, batch_id: str) -> None:
    db.flush()
    batch = db.get(Batch, batch_id)
    if not batch:
        return
    batch.processed_documents = db.query(Document).filter(Document.batch_id == batch_id, Document.status.in_(["pending_review", "verified"])).count()
    batch.failed_documents = db.query(Document).filter(Document.batch_id == batch_id, Document.status == "failed").count()


def process_document(document_id: str, provider: TrOCRProvider | None = None) -> None:
    provider = provider or get_provider()
    with SessionLocal() as db:
        document = db.get(Document, document_id)
        if not document:
            return
        batch = db.get(Batch, document.batch_id)
        template = db.get(FormTemplate, batch.template_id) if batch else None
        if not batch or not template:
            document.status = "failed"
            document.error_message = "The document batch or selected form template is missing."
            refresh_batch_counts(db, document.batch_id)
            db.commit()
            return
        document.status = "processing"
        document.error_message = None
        refresh_batch_counts(db, document.batch_id)
        db.commit()
        record = db.scalar(select(StudentRecord).where(StudentRecord.document_id == document.id))
        if not record:
            record = StudentRecord(document_id=document.id, template_id=template.id, verification_status="pending")
            db.add(record)
            db.flush()
        questions = db.scalars(select(Question).where(Question.template_id == template.id).order_by(Question.display_order)).all()
        source = Path(document.stored_path)
        if not source.is_absolute():
            source = PROJECT_ROOT / source
        processed_dir = PROJECT_ROOT / "local_data" / "processed" / document.id
        shutil.rmtree(processed_dir, ignore_errors=True)
        processed_dir.mkdir(parents=True, exist_ok=True)
        try:
            if source.suffix.lower() == ".pdf":
                pages = render_pdf(source, processed_dir / "pages")
                page_paths = {index + 1: page for index, page in enumerate(pages)}
            else:
                page_paths = {1: source}
            document.page_count = len(page_paths)
            pages_dir = processed_dir / "aligned-pages"
            pages_dir.mkdir(exist_ok=True)
            current_page = 0
            current_image = None
            template_image = None
            for question in questions:
                answer = db.scalar(select(Answer).where(Answer.student_record_id == record.id, Answer.question_id == question.id))
                if not answer:
                    answer = Answer(student_record_id=record.id, question_id=question.id, page_number=question.page_number, verification_status="recognition_failed")
                    db.add(answer)
                if answer.verification_status == "verified":
                    continue
                coords = (question.region_x, question.region_y, question.region_width, question.region_height)
                if question.page_number not in page_paths or any(value is None for value in coords):
                    answer.raw_ocr_text = ""
                    answer.normalized_ocr_text = ""
                    answer.ocr_model = None
                    answer.verification_status = "recognition_failed"
                    continue
                if current_page != question.page_number:
                    current_image = load_image(page_paths[question.page_number])
                    current_image, _ = correct_document_perspective(current_image)
                    sample = db.get(TemplateSample, (template.id, question.page_number))
                    template_image = load_image(PROJECT_ROOT / sample.stored_path) if sample else None
                    if template_image is None:
                        raise ValueError(f"Template page {question.page_number} has no saved sample image. Upload it and map its regions before processing.")
                    current_image = align_to_template(current_image, template_image)
                    if not cv2.imwrite(str(pages_dir / f"page-{question.page_number:03d}.png"), current_image):
                        raise OSError("Could not store aligned document page")
                    current_page = question.page_number
                crop = crop_region(current_image, coords)
                crop_path = processed_dir / f"question-{question.id}.png"
                if not cv2.imwrite(str(crop_path), crop):
                    raise OSError("Could not store processed answer region")
                line_crops = segment_lines(crop_path, processed_dir / f"lines-{question.id}")
                output = [provider.recognize_line(line.path) for line in line_crops]
                answer.raw_ocr_text = "\n".join(item.raw_text for item in output)
                answer.normalized_ocr_text = " ".join(item.normalized_text for item in output)
                answer.ocr_model = output[0].model if output else None
                confidences = [item.confidence for item in output if item.confidence is not None]
                answer.confidence_score = sum(confidences) / len(confidences) if confidences else None
                answer.verification_status = "needs_review" if answer.normalized_ocr_text else "recognition_failed"
            record.verification_status = "pending"
            document.status = "pending_review"
            document.error_message = None
        except Exception as exc:
            document.status = "failed"
            document.error_message = str(exc)[:1000]
            for answer in record.answers:
                answer.verification_status = "recognition_failed"
        refresh_batch_counts(db, document.batch_id)
        db.commit()


def process_batch(batch_id: str, provider: TrOCRProvider | None = None) -> None:
    """Process a batch sequentially, keeping the model provider reusable."""
    provider = provider or get_provider()
    with SessionLocal() as db:
        batch = db.get(Batch, batch_id)
        if not batch:
            return
        ids = list(db.scalars(select(Document.id).where(Document.batch_id == batch_id, Document.status.in_(["uploaded", "queued", "failed"]))))
    for document_id in ids:
        process_document(document_id, provider)
    with SessionLocal() as db:
        batch = db.get(Batch, batch_id)
        if batch:
            refresh_batch_counts(db, batch_id)
            db.commit()
