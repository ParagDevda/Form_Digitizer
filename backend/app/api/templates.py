"""Template and question management endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import FormTemplate, Question
from app.schemas import QuestionCreate, QuestionRead, QuestionUpdate, TemplateCreate, TemplateRead, TemplateUpdate

router = APIRouter(prefix="/api/templates", tags=["templates"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


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


@router.put("/{template_id}", response_model=TemplateRead)
def update_template(template_id: str, payload: TemplateUpdate, db: Session = Depends(get_db)):
    template = db.get(FormTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
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
    if not db.get(FormTemplate, template_id):
        raise HTTPException(status_code=404, detail="Template not found")
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
    for key, value in payload.model_dump(exclude_unset=True).items():
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
