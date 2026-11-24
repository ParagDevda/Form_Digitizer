"""Student record review and correction endpoints."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.database import PROJECT_ROOT, SessionLocal
from app.models import Answer, Batch, Document, FormTemplate, Question, StudentRecord

router = APIRouter(prefix="/api", tags=["records"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class AnswerCorrection(BaseModel):
    corrected_text: str = Field(max_length=20000)
    verification_status: str = Field(default="verified", pattern="^(verified|needs_review|recognition_failed)$")


class RecordUpdate(BaseModel):
    student_name: str | None = Field(default=None, max_length=250)
    student_identifier: str | None = Field(default=None, max_length=160)


@router.get("/records")
def list_records(q: str | None = Query(default=None, max_length=250), status: str | None = None, template_id: str | None = None, batch_id: str | None = None, db: Session = Depends(get_db)):
    query = select(StudentRecord).join(Document, Document.id == StudentRecord.document_id).options(selectinload(StudentRecord.answers)).order_by(StudentRecord.created_at.desc()).limit(2000)
    if q and q.strip():
        term = f"%{q.strip()}%"
        query = query.where(or_(StudentRecord.student_name.ilike(term), StudentRecord.student_identifier.ilike(term), Document.original_filename.ilike(term)))
    if status:
        query = query.where(StudentRecord.verification_status == status)
    if template_id:
        query = query.where(StudentRecord.template_id == template_id)
    if batch_id:
        query = query.where(Document.batch_id == batch_id)
    records = db.scalars(query).all()
    results = []
    for record in records:
        document = db.get(Document, record.document_id)
        batch = db.get(Batch, document.batch_id) if document else None
        template = db.get(FormTemplate, record.template_id)
        results.append({"id": record.id, "document_id": record.document_id, "filename": document.original_filename if document else None, "batch_id": batch.id if batch else None, "batch_name": batch.batch_name if batch else None, "template_id": record.template_id, "template_name": template.name if template else None, "student_name": record.student_name, "student_identifier": record.student_identifier, "document_status": document.status if document else "missing", "verification_status": record.verification_status, "answer_count": len(record.answers), "created_at": record.created_at})
    return results


@router.get("/records/{record_id}")
def get_record(record_id: str, db: Session = Depends(get_db)):
    record = db.scalar(select(StudentRecord).options(selectinload(StudentRecord.answers)).where(StudentRecord.id == record_id))
    if not record:
        raise HTTPException(status_code=404, detail="Student record not found")
    doc = db.get(Document, record.document_id)
    template = db.get(FormTemplate, record.template_id)
    batch = db.get(Batch, doc.batch_id) if doc else None
    answers = []
    for answer in record.answers:
        question = db.get(Question, answer.question_id)
        answers.append({"id": answer.id, "question_id": answer.question_id, "question_number": question.question_number if question else None, "question_text": question.question_text if question else "(question removed)", "page_number": answer.page_number, "region_x": question.region_x if question else None, "region_y": question.region_y if question else None, "region_width": question.region_width if question else None, "region_height": question.region_height if question else None, "raw_ocr_text": answer.raw_ocr_text, "normalized_ocr_text": answer.normalized_ocr_text, "corrected_text": answer.corrected_text, "confidence_score": answer.confidence_score, "verification_status": answer.verification_status, "ocr_model": answer.ocr_model})
    return {"id": record.id, "document_id": record.document_id, "filename": doc.original_filename if doc else None, "batch_name": batch.batch_name if batch else None, "template_name": template.name if template else None, "student_name": record.student_name, "student_identifier": record.student_identifier, "verification_status": record.verification_status, "answers": answers}


@router.put("/records/{record_id}")
def update_record(record_id: str, payload: RecordUpdate, db: Session = Depends(get_db)):
    record = db.get(StudentRecord, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Student record not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(record, key, value.strip() if isinstance(value, str) else value)
    db.commit()
    return {"id": record.id, "student_name": record.student_name, "student_identifier": record.student_identifier}


@router.delete("/records/{record_id}", status_code=204)
def delete_record(record_id: str, db: Session = Depends(get_db)):
    record = db.get(StudentRecord, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Student record not found")
    document = db.get(Document, record.document_id)
    if document and document.status in {"queued", "processing"}:
        raise HTTPException(status_code=409, detail="A queued or processing document cannot be deleted")
    source = Path(document.stored_path) if document else None
    if source and not source.is_absolute():
        source = PROJECT_ROOT / source
    batch = db.get(Batch, document.batch_id) if document else None
    if document:
        db.delete(document)
        if batch:
            batch.total_documents = max(0, batch.total_documents - 1)
            batch.processed_documents = max(0, batch.processed_documents - int(document.status in {"pending_review", "verified"}))
            batch.failed_documents = max(0, batch.failed_documents - int(document.status == "failed"))
    db.delete(record)
    db.commit()
    if source:
        source.unlink(missing_ok=True)
    if document:
        import shutil
        shutil.rmtree(PROJECT_ROOT / "local_data" / "processed" / document.id, ignore_errors=True)
    return Response(status_code=204)


@router.put("/answers/{answer_id}")
def update_answer(answer_id: str, payload: AnswerCorrection, db: Session = Depends(get_db)):
    answer = db.get(Answer, answer_id)
    if not answer:
        raise HTTPException(status_code=404, detail="Answer not found")
    answer.corrected_text = payload.corrected_text
    answer.verification_status = payload.verification_status
    db.commit()
    return {"id": answer.id, "corrected_text": answer.corrected_text, "verification_status": answer.verification_status}


@router.post("/records/{record_id}/verify")
def verify_record(record_id: str, db: Session = Depends(get_db)):
    record = db.get(StudentRecord, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Student record not found")
    answers = db.scalars(select(Answer).where(Answer.student_record_id == record.id)).all()
    if not answers or any(answer.verification_status != "verified" for answer in answers):
        raise HTTPException(status_code=409, detail="Every answer must be reviewed before verifying the record")
    record.verification_status = "verified"
    document = db.get(Document, record.document_id)
    if document:
        document.status = "verified"
    db.commit()
    return {"id": record.id, "verification_status": record.verification_status}


@router.get("/documents/{document_id}/file")
def get_document_page(document_id: str, page: int = 1, db: Session = Depends(get_db)):
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    source = Path(document.stored_path)
    if not source.is_absolute():
        source = PROJECT_ROOT / source
    if not source.is_file() or page < 1 or page > document.page_count:
        raise HTTPException(status_code=404, detail="Document page not found")
    if source.suffix.lower() != ".pdf":
        if page != 1:
            raise HTTPException(status_code=404, detail="Document page not found")
        return FileResponse(source)
    import fitz
    try:
        with fitz.open(source) as pdf:
            pixmap = pdf[page - 1].get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            return FileResponse(_write_preview(pixmap, document_id, page), media_type="image/png")
    except (IndexError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail="Could not render this PDF page") from exc


def _write_preview(pixmap, document_id: str, page: int) -> Path:
    target_dir = PROJECT_ROOT / "local_data" / "processed" / document_id / "preview"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"page-{page:03d}.png"
    pixmap.save(target)
    return target
