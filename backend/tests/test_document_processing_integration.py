from pathlib import Path
from uuid import uuid4

import cv2
import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Batch, Document, FormTemplate, Question, TemplateSample
from app.services import document_processing
from app.services.ocr.trocr import TrOCRProvider


@pytest.mark.integration
def test_local_trocr_processes_aligned_form_region(tmp_path, monkeypatch):
    model_path = Path(__file__).resolve().parents[1] / "models" / "trocr-base-handwritten"
    if not model_path.is_dir():
        pytest.skip("Local TrOCR model has not been provisioned")

    engine = create_engine(f"sqlite:///{tmp_path / 'processing-test.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(document_processing, "SessionLocal", factory)
    monkeypatch.setattr(document_processing, "PROJECT_ROOT", tmp_path)

    sample = np.full((1000, 800, 3), 255, dtype=np.uint8)
    for index, y in enumerate(range(90, 820, 70), 1):
        cv2.putText(sample, f"Question {index} provide the following information", (45, y), cv2.FONT_HERSHEY_SIMPLEX, .68, (0, 0, 0), 2)
        cv2.line(sample, (40, y + 12), (750, y + 12), (0, 0, 0), 1)
    filled = sample.copy()
    cv2.putText(filled, "Jordan Smith", (48, 945), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2)

    sample_path = tmp_path / "local_data" / "templates" / "sample.png"
    form_path = tmp_path / "local_data" / "documents" / "form.png"
    sample_path.parent.mkdir(parents=True); form_path.parent.mkdir(parents=True)
    cv2.imwrite(str(sample_path), sample); cv2.imwrite(str(form_path), filled)
    batch_id, document_id = str(uuid4()), str(uuid4())
    with factory.begin() as db:
        template = FormTemplate(name="Integration form", page_count=1)
        db.add(template); db.flush()
        db.add(TemplateSample(template_id=template.id, stored_path=str(sample_path.relative_to(tmp_path)), original_filename="sample.png"))
        db.add(Question(template_id=template.id, question_number=1, question_text="Student name", answer_type="short_text", is_required=True, display_order=0, page_number=1, region_x=.025, region_y=.86, region_width=.95, region_height=.13))
        db.add(Batch(id=batch_id, batch_name="Integration", template_id=template.id, total_documents=1))
        db.add(Document(id=document_id, batch_id=batch_id, original_filename="form.png", stored_path=str(form_path.relative_to(tmp_path)), file_hash="a" * 64, status="uploaded", page_count=1))
    document_processing.process_document(document_id, TrOCRProvider(model_path))
    with factory() as db:
        document = db.get(Document, document_id)
        assert document.status == "pending_review", document.error_message
        assert db.get(Batch, batch_id).processed_documents == 1
        from app.models import Answer
        answer = db.query(Answer).one()
        assert answer.normalized_ocr_text.strip()
        assert answer.ocr_model == "microsoft/trocr-base-handwritten"
    engine.dispose()
