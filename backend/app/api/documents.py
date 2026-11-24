"""Batch creation and local document upload endpoints."""

import hashlib
import os
import tempfile
from pathlib import Path
from uuid import uuid4

import fitz
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import PROJECT_ROOT, SessionLocal
from app.models import Batch, Document, FormTemplate, Question, TemplateSample
from app.services.processing_queue import processing_queue

router = APIRouter(prefix="/api", tags=["documents"])
ALLOWED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".pdf"}
MAX_FILE_BYTES = 25 * 1024 * 1024
MAX_BATCH_DOCUMENTS = 500


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/batches", status_code=status.HTTP_201_CREATED)
def create_batch(batch_name: str = Form(min_length=1, max_length=160), template_id: str = Form(), db: Session = Depends(get_db)):
    if not db.get(FormTemplate, template_id):
        raise HTTPException(status_code=404, detail="Template not found")
    batch = Batch(batch_name=batch_name.strip(), template_id=template_id)
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return {"id": batch.id, "batch_name": batch.batch_name, "template_id": batch.template_id, "total_documents": 0, "processed_documents": 0, "failed_documents": 0}


@router.get("/batches")
def list_batches(db: Session = Depends(get_db)):
    batches = db.scalars(select(Batch).order_by(Batch.created_at.desc()).limit(2000)).all()
    return [{"id": batch.id, "name": batch.batch_name, "total_documents": batch.total_documents, "processed_documents": batch.processed_documents, "failed_documents": batch.failed_documents, "created_at": batch.created_at} for batch in batches]


def validate_document(path: Path, suffix: str) -> int:
    try:
        if suffix == ".pdf":
            with fitz.open(path) as pdf:
                if pdf.page_count < 1 or pdf.page_count > 100:
                    raise ValueError("PDF must contain between 1 and 100 pages")
                for page in pdf:
                    width, height = page.rect.width * 180 / 72, page.rect.height * 180 / 72
                    if width > 7000 or height > 7000 or width * height > 40_000_000:
                        raise ValueError("PDF page dimensions exceed the supported processing limit")
                return pdf.page_count
        with Image.open(path) as image:
            if image.width > 12000 or image.height > 12000 or image.width * image.height > 40_000_000:
                raise ValueError("Image dimensions exceed the supported processing limit")
            image.verify()
        with Image.open(path) as image:
            image.load()
        return 1
    except (OSError, fitz.FileDataError) as exc:
        raise ValueError("File is not a valid image or PDF") from exc


@router.post("/documents/upload", status_code=status.HTTP_201_CREATED)
async def upload_documents(batch_id: str = Form(), files: list[UploadFile] = File(), db: Session = Depends(get_db)):
    batch = db.get(Batch, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    if batch.total_documents + len(files) > MAX_BATCH_DOCUMENTS:
        raise HTTPException(status_code=413, detail=f"A batch can contain at most {MAX_BATCH_DOCUMENTS} documents")
    results = []
    for upload in files:
        suffix = Path(upload.filename or "").suffix.lower()
        if suffix not in ALLOWED_SUFFIXES:
            raise HTTPException(status_code=415, detail=f"Unsupported file format: {suffix or 'unknown'}")
        stored_dir = PROJECT_ROOT / "local_data" / "documents" / batch.id
        stored_dir.mkdir(parents=True, exist_ok=True)
        temp_path = stored_dir / f".{uuid4()}.upload"
        digest = hashlib.sha256()
        size = 0
        try:
            with temp_path.open("wb") as target:
                while chunk := await upload.read(1024 * 1024):
                    size += len(chunk)
                    if size > MAX_FILE_BYTES:
                        raise HTTPException(status_code=413, detail=f"{upload.filename} exceeds the 25 MB limit")
                    digest.update(chunk)
                    target.write(chunk)
            file_hash = digest.hexdigest()
            existing = db.scalar(select(Document.id).where(Document.file_hash == file_hash))
            if existing:
                raise HTTPException(status_code=409, detail=f"Duplicate file already uploaded as document {existing}")
            page_count = validate_document(temp_path, suffix)
            document_id = str(uuid4())
            safe_name = Path(upload.filename or "document").name[:240]
            final_path = stored_dir / f"{document_id}{suffix}"
            os.replace(temp_path, final_path)
            document = Document(id=document_id, batch_id=batch.id, original_filename=safe_name, stored_path=str(final_path.relative_to(PROJECT_ROOT)), file_hash=file_hash, status="uploaded", page_count=page_count)
            db.add(document)
            batch.total_documents += 1
            db.commit()
            results.append({"id": document.id, "filename": safe_name, "status": document.status, "page_count": page_count})
        except ValueError as exc:
            db.rollback()
            raise HTTPException(status_code=422, detail=f"{upload.filename}: {exc}") from exc
        finally:
            temp_path.unlink(missing_ok=True)
            await upload.close()
    return {"batch_id": batch.id, "uploaded": len(results), "documents": results}


@router.get("/documents")
def list_documents(batch_id: str | None = None, db: Session = Depends(get_db)):
    query = select(Document).order_by(Document.created_at.desc())
    if batch_id:
        query = query.where(Document.batch_id == batch_id)
    documents = db.scalars(query.limit(1000)).all()
    return [{"id": d.id, "batch_id": d.batch_id, "filename": d.original_filename, "status": d.status, "page_count": d.page_count, "error_message": d.error_message, "created_at": d.created_at} for d in documents]


@router.get("/documents/{document_id}")
def get_document(document_id: str, db: Session = Depends(get_db)):
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"id": document.id, "batch_id": document.batch_id, "filename": document.original_filename, "status": document.status, "page_count": document.page_count, "error_message": document.error_message}


@router.post("/batches/{batch_id}/process", status_code=status.HTTP_202_ACCEPTED)
def start_batch_processing(batch_id: str, db: Session = Depends(get_db)):
    batch = db.get(Batch, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    if batch.total_documents == 0:
        raise HTTPException(status_code=409, detail="Batch has no uploaded documents")
    template = db.get(FormTemplate, batch.template_id)
    questions = db.scalars(select(Question).where(Question.template_id == batch.template_id)).all()
    if not questions:
        raise HTTPException(status_code=409, detail="Add questions and map their answer regions before processing")
    missing_pages = sorted({question.page_number for question in questions if question.region_x is None} | {page for page in range(1, (template.page_count if template else 0) + 1) if db.get(TemplateSample, (batch.template_id, page)) is None and any(question.page_number == page for question in questions)})
    if missing_pages:
        pages = ", ".join(str(page) for page in missing_pages)
        raise HTTPException(status_code=409, detail=f"Map answer regions and upload a blank sample for template page(s): {pages}")
    processing_queue.submit(batch_id)
    return {"batch_id": batch_id, "status": "queued"}


@router.get("/batches/{batch_id}/status")
def get_batch_status(batch_id: str, db: Session = Depends(get_db)):
    batch = db.get(Batch, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    return {"id": batch.id, "batch_name": batch.batch_name, "total_documents": batch.total_documents, "processed_documents": batch.processed_documents, "failed_documents": batch.failed_documents, "documents": [{"id": d.id, "filename": d.original_filename, "status": d.status, "error": d.error_message} for d in batch.documents]}


@router.post("/documents/{document_id}/retry", status_code=status.HTTP_202_ACCEPTED)
def retry_document(document_id: str, db: Session = Depends(get_db)):
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    if document.status == "processing":
        raise HTTPException(status_code=409, detail="Document is already processing")
    document.status = "queued"
    document.error_message = None
    db.commit()
    processing_queue.submit(document.batch_id)
    return {"document_id": document.id, "status": "queued"}


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: str, db: Session = Depends(get_db)):
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    batch = db.get(Batch, document.batch_id)
    if document.status in {"queued", "processing"}:
        raise HTTPException(status_code=409, detail="A queued or processing document cannot be deleted")
    source = Path(document.stored_path if Path(document.stored_path).is_absolute() else PROJECT_ROOT / document.stored_path)
    document_dir = PROJECT_ROOT / "local_data" / "processed" / document.id
    db.delete(document)
    if batch:
        batch.total_documents = max(0, batch.total_documents - 1)
        batch.processed_documents = max(0, batch.processed_documents - int(document.status in {"pending_review", "verified"}))
        batch.failed_documents = max(0, batch.failed_documents - int(document.status == "failed"))
    db.commit()
    source.unlink(missing_ok=True)
    import shutil
    shutil.rmtree(document_dir, ignore_errors=True)
