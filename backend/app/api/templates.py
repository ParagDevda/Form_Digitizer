"""Template and question management endpoints."""

import os
import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import PROJECT_ROOT, SessionLocal
from app.models import FormTemplate, Question, TemplateSample
from app.schemas import QuestionCreate, QuestionRead, QuestionUpdate, TemplateCreate, TemplateRead, TemplateUpdate

router = APIRouter(prefix="/api/templates", tags=["templates"])
SAMPLE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/{template_id}/sample", status_code=status.HTTP_201_CREATED)
async def upload_template_sample(template_id: str, file: UploadFile = File(...), db: Session = Depends(get_db)):
    template = db.get(FormTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in SAMPLE_SUFFIXES:
        raise HTTPException(status_code=415, detail="Sample must be a JPG, PNG, or WEBP image")
    directory = PROJECT_ROOT / "local_data" / "templates" / template_id
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f"sample-{uuid4()}{suffix}"
    size = 0
    try:
        with destination.open("wb") as output:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > 25 * 1024 * 1024:
                    raise HTTPException(status_code=413, detail="Template sample exceeds 25 MB")
                output.write(chunk)
        from PIL import Image
        with Image.open(destination) as image:
            image.verify()
        old = db.get(TemplateSample, template_id)
        if old:
            old_path = PROJECT_ROOT / old.stored_path
            old_path.unlink(missing_ok=True)
            old.stored_path = str(destination.relative_to(PROJECT_ROOT))
            old.original_filename = Path(file.filename or "sample").name[:240]
        else:
            db.add(TemplateSample(template_id=template_id, stored_path=str(destination.relative_to(PROJECT_ROOT)), original_filename=Path(file.filename or "sample").name[:240]))
        db.commit()
        return {"template_id": template_id, "filename": Path(file.filename or "sample").name}
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    finally:
        await file.close()


@router.get("/{template_id}/sample")
def get_template_sample(template_id: str, db: Session = Depends(get_db)):
    sample = db.get(TemplateSample, template_id)
    if not sample:
        raise HTTPException(status_code=404, detail="Template sample not uploaded")
    path = PROJECT_ROOT / sample.stored_path
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Template sample file is missing")
    return FileResponse(path)


@router.get("", response_model=list[TemplateRead])
def list_templates(db: Session = Depends(get_db)):
    return db.scalars(select(FormTemplate).order_by(FormTemplate.updated_at.desc())).all()


@router.post("", response_model=TemplateRead, status_code=status.HTTP_201_CREATED)
def create_template(payload: TemplateCreate, db: Session = Depends(get_db)):
    template = FormTemplate(**payload.model_dump())
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


@router.get("/{template_id}", response_model=TemplateRead)
def get_template(template_id: str, db: Session = Depends(get_db)):
    template = db.get(FormTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


@router.post("/{template_id}/duplicate", response_model=TemplateRead, status_code=status.HTTP_201_CREATED)
def duplicate_template(template_id: str, db: Session = Depends(get_db)):
    source = db.get(FormTemplate, template_id)
    if not source:
        raise HTTPException(status_code=404, detail="Template not found")
    duplicate = FormTemplate(id=str(uuid4()), name=f"Copy of {source.name}"[:160], description=source.description, version=source.version, page_count=source.page_count)
    duplicate.questions = [Question(question_number=q.question_number, question_text=q.question_text, answer_type=q.answer_type, is_required=q.is_required, display_order=q.display_order, page_number=q.page_number, region_x=q.region_x, region_y=q.region_y, region_width=q.region_width, region_height=q.region_height) for q in source.questions]
    copied_sample = None
    if source.sample:
        source_path = PROJECT_ROOT / source.sample.stored_path
        if source_path.is_file():
            target_dir = PROJECT_ROOT / "local_data" / "templates" / duplicate.id
            target_dir.mkdir(parents=True, exist_ok=True)
            copied_sample = target_dir / f"sample{source_path.suffix}"
            shutil.copy2(source_path, copied_sample)
            duplicate.sample = TemplateSample(template_id=duplicate.id, stored_path=str(copied_sample.relative_to(PROJECT_ROOT)), original_filename=source.sample.original_filename)
    db.add(duplicate)
    db.commit()
    db.refresh(duplicate)
    return duplicate


@router.put("/{template_id}", response_model=TemplateRead)
def update_template(template_id: str, payload: TemplateUpdate, db: Session = Depends(get_db)):
    template = db.get(FormTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    updates = payload.model_dump(exclude_unset=True)
    if "page_count" in updates:
        highest_page = max((q.page_number for q in template.questions), default=1)
        if updates["page_count"] < highest_page:
            raise HTTPException(status_code=409, detail="Page count cannot be lower than a question's page number")
    for key, value in updates.items():
        setattr(template, key, value)
    db.commit()
    db.refresh(template)
    return template


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_template(template_id: str, db: Session = Depends(get_db)):
    template = db.get(FormTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    db.delete(template)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{template_id}/questions", response_model=QuestionRead, status_code=status.HTTP_201_CREATED)
def add_question(template_id: str, payload: QuestionCreate, db: Session = Depends(get_db)):
    template = db.get(FormTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    if payload.page_number > template.page_count:
        raise HTTPException(status_code=422, detail="Question page exceeds the template page count")
    question = Question(template_id=template_id, **payload.model_dump())
    db.add(question)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Question number already exists in this template")
    db.refresh(question)
    return question


@router.put("/questions/{question_id}", response_model=QuestionRead)
def update_question(question_id: str, payload: QuestionUpdate, db: Session = Depends(get_db)):
    question = db.get(Question, question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    updates = payload.model_dump(exclude_unset=True)
    if updates.get("page_number", question.page_number) > question.template.page_count:
        raise HTTPException(status_code=422, detail="Question page exceeds the template page count")
    for key, value in updates.items():
        setattr(question, key, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Question number already exists in this template")
    db.refresh(question)
    return question


@router.delete("/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_question(question_id: str, db: Session = Depends(get_db)):
    question = db.get(Question, question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    db.delete(question)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
