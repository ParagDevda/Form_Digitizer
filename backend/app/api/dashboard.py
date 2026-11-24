"""Local dashboard counts and recent batches."""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.documents import get_db
from app.models import Batch, Document, FormTemplate, StudentRecord

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats")
def dashboard_stats(db: Session = Depends(get_db)):
    def count(model, *filters):
        return db.scalar(select(func.count()).select_from(model).where(*filters)) or 0

    return {
        "uploaded_forms": count(Document),
        "processed_forms": count(Document, Document.status.in_(["pending_review", "verified"])),
        "verified_forms": count(Document, Document.status == "verified"),
        "pending_review": count(Document, Document.status == "pending_review"),
        "failed_forms": count(Document, Document.status == "failed"),
        "student_records": count(StudentRecord),
        "templates": count(FormTemplate),
        "batches": count(Batch),
    }


@router.get("/batches")
def recent_batches(db: Session = Depends(get_db)):
    batches = db.scalars(select(Batch).order_by(Batch.created_at.desc()).limit(8)).all()
    return [{"id": b.id, "name": b.batch_name, "total_documents": b.total_documents, "processed_documents": b.processed_documents, "failed_documents": b.failed_documents, "created_at": b.created_at} for b in batches]
