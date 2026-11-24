"""Question-wise local Excel export endpoints."""

from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import PROJECT_ROOT, SessionLocal
from app.models import Answer, Document, FormTemplate, Question, StudentRecord

router = APIRouter(prefix="/api/export", tags=["exports"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class ExportRequest(BaseModel):
    template_ids: list[str] | None = None
    record_ids: list[str] | None = None
    batch_id: str | None = None
    verified_only: bool = False


@router.post("")
def create_export(payload: ExportRequest, db: Session = Depends(get_db)):
    query = select(StudentRecord).options(selectinload(StudentRecord.answers)).order_by(StudentRecord.created_at)
    if payload.record_ids is not None:
        query = query.where(StudentRecord.id.in_(payload.record_ids))
    if payload.template_ids is not None:
        query = query.where(StudentRecord.template_id.in_(payload.template_ids))
    if payload.batch_id:
        query = query.join(Document, Document.id == StudentRecord.document_id).where(Document.batch_id == payload.batch_id)
    if payload.verified_only:
        query = query.where(StudentRecord.verification_status == "verified")
    records = db.scalars(query).all()
    selected_ids = set(payload.template_ids or [r.template_id for r in records])
    templates = db.scalars(select(FormTemplate).where(FormTemplate.id.in_(selected_ids))).all() if selected_ids else []
    if not templates:
        raise HTTPException(status_code=404, detail="No matching templates or student records to export")
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    workbook = Workbook()
    workbook.remove(workbook.active)
    used_titles: set[str] = set()
    for template in templates:
        questions = db.scalars(select(Question).where(Question.template_id == template.id).order_by(Question.display_order)).all()
        base_title = "".join(" " if character in "[]:*?/\\" else character for character in template.name).strip(" '\t")[:31] or "Student records"
        title, suffix = base_title, 2
        while title.casefold() in used_titles:
            ending = f" ({suffix})"
            title = f"{base_title[:31 - len(ending)]}{ending}"
            suffix += 1
        used_titles.add(title.casefold())
        sheet = workbook.create_sheet(title)
        headers = ["Student record", "Student name", "Student identifier", "Source file", "Verification status"] + [f"Q{q.question_number}: {q.question_text}" for q in questions]
        sheet.append(headers)
        for record in records:
            if record.template_id != template.id:
                continue
            document = record.document
            answers = {a.question_id: a for a in record.answers}
            cells = [record.id, record.student_name or "", record.student_identifier or "", document.original_filename if document else "", record.verification_status]
            cells.extend((answers[q.id].corrected_text if answers[q.id].corrected_text is not None else answers[q.id].normalized_ocr_text) if q.id in answers else "" for q in questions)
            sheet.append(cells)
        for cell in sheet[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="315CA8")
            cell.alignment = Alignment(wrap_text=True, vertical="top")
        sheet.freeze_panes = "F2"
        sheet.auto_filter.ref = sheet.dimensions
        for column in sheet.columns:
            letter = get_column_letter(column[0].column)
            sheet.column_dimensions[letter].width = min(48, max(14, max(len(str(cell.value or "")) for cell in column) + 2))
        for row in sheet.iter_rows(min_row=2):
            for cell in row:
                cell.alignment = Alignment(wrap_text=True, vertical="top")
    directory = PROJECT_ROOT / "local_data" / "exports"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"student-forms-{datetime.now():%Y%m%d-%H%M%S}-{uuid4().hex[:8]}.xlsx"
    workbook.save(path)
    return FileResponse(path, filename=path.name, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
