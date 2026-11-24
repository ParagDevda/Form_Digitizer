from collections.abc import Iterator

import fitz
import pytest
import sqlite3
import zipfile
from uuid import uuid4
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.main import app
from app.api.documents import get_db as documents_db
from app.api.records import get_db as records_db
from app.api.templates import get_db as templates_db
from app.api.exports import get_db as exports_db
from app.api.templates import get_db as template_files_db
from openpyxl import load_workbook
from io import BytesIO
from app.models import Answer, Batch, Document, FormTemplate, Question, StudentRecord


@pytest.fixture()
def client(tmp_path, monkeypatch) -> Iterator[TestClient]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_db():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    monkeypatch.setattr("app.api.documents.PROJECT_ROOT", tmp_path)
    monkeypatch.setattr("app.api.exports.PROJECT_ROOT", tmp_path)
    monkeypatch.setattr("app.api.templates.PROJECT_ROOT", tmp_path)
    monkeypatch.setattr("app.api.settings.PROJECT_ROOT", tmp_path)
    monkeypatch.setattr("app.services.document_processing.PROJECT_ROOT", tmp_path)
    app.dependency_overrides[documents_db] = override_db
    app.dependency_overrides[records_db] = override_db
    app.dependency_overrides[templates_db] = override_db
    app.dependency_overrides[exports_db] = override_db
    app.dependency_overrides[template_files_db] = override_db
    with TestClient(app) as test_client:
        test_client.app.state.test_session_factory = factory
        yield test_client
    app.dependency_overrides.clear()
    engine.dispose()


def test_template_question_crud_and_region_validation(client):
    created = client.post("/api/templates", json={"name": "Intake", "page_count": 1})
    assert created.status_code == 201
    template_id = created.json()["id"]
    question = client.post(f"/api/templates/{template_id}/questions", json={"question_number": 1, "question_text": "Student name", "display_order": 0, "region_x": .1, "region_y": .2, "region_width": .5, "region_height": .1})
    assert question.status_code == 201
    assert question.json()["region_x"] == .1
    invalid = client.post(f"/api/templates/{template_id}/questions", json={"question_number": 2, "question_text": "Bad region", "display_order": 1, "region_x": .8, "region_y": .2, "region_width": .5, "region_height": .1})
    assert invalid.status_code == 422
    assert client.get(f"/api/templates/{template_id}").json()["questions"][0]["question_text"] == "Student name"


def test_question_region_update_must_be_complete(client):
    template = client.post("/api/templates", json={"name": "Region update"}).json()
    question = client.post(f"/api/templates/{template['id']}/questions", json={"question_number": 1, "question_text": "Name", "display_order": 0}).json()
    partial = client.put(f"/api/templates/questions/{question['id']}", json={"region_x": .1})
    assert partial.status_code == 422
    complete = client.put(f"/api/templates/questions/{question['id']}", json={"region_x": .1, "region_y": .2, "region_width": .4, "region_height": .1})
    assert complete.status_code == 200


def test_template_duplicate_copies_question_configuration(client):
    template = client.post("/api/templates", json={"name": "Questionnaire", "page_count": 2}).json()
    client.post(f"/api/templates/{template['id']}/questions", json={"question_number": 1, "question_text": "Name", "display_order": 0, "page_number": 2})
    duplicate = client.post(f"/api/templates/{template['id']}/duplicate")
    assert duplicate.status_code == 201
    copy = duplicate.json()
    assert copy["name"] == "Copy of Questionnaire"
    assert copy["questions"][0]["question_text"] == "Name"
    assert copy["questions"][0]["page_number"] == 2


def test_template_cannot_be_shrunk_below_question_page(client):
    template = client.post("/api/templates", json={"name": "Two pages", "page_count": 2}).json()
    client.post(f"/api/templates/{template['id']}/questions", json={"question_number": 1, "question_text": "Back page", "display_order": 0, "page_number": 2})
    response = client.put(f"/api/templates/{template['id']}", json={"page_count": 1})
    assert response.status_code == 409


def test_template_samples_are_saved_per_page(client):
    template = client.post("/api/templates", json={"name": "Two page form", "page_count": 2}).json()
    for page in (1, 2):
        image_bytes = BytesIO()
        Image.new("RGB", (50, 60), "white").save(image_bytes, format="PNG")
        response = client.post(f"/api/templates/{template['id']}/sample?page_number={page}", files={"file": (f"page-{page}.png", image_bytes.getvalue(), "image/png")})
        assert response.status_code == 201
        assert client.get(f"/api/templates/{template['id']}/sample?page_number={page}").status_code == 200
    assert client.get(f"/api/templates/{template['id']}/sample?page_number=3").status_code == 404


def test_upload_valid_image_and_reject_duplicate(client):
    template = client.post("/api/templates", json={"name": "Intake"}).json()
    batch = client.post("/api/batches", data={"batch_name": "November", "template_id": template["id"]}).json()
    image_bytes = __import__("io").BytesIO()
    Image.new("RGB", (32, 32), "white").save(image_bytes, format="PNG")
    payload = image_bytes.getvalue()
    first = client.post("/api/documents/upload", data={"batch_id": batch["id"]}, files={"files": ("form.png", payload, "image/png")})
    assert first.status_code == 201
    duplicate = client.post("/api/documents/upload", data={"batch_id": batch["id"]}, files={"files": ("copy.png", payload, "image/png")})
    assert duplicate.status_code == 409


def test_upload_pdf_counts_pages(client):
    template = client.post("/api/templates", json={"name": "Intake"}).json()
    batch = client.post("/api/batches", data={"batch_name": "PDF", "template_id": template["id"]}).json()
    pdf = fitz.open()
    pdf.new_page(); pdf.new_page()
    payload = pdf.tobytes(); pdf.close()
    response = client.post("/api/documents/upload", data={"batch_id": batch["id"]}, files={"files": ("two-pages.pdf", payload, "application/pdf")})
    assert response.status_code == 201
    assert response.json()["documents"][0]["page_count"] == 2


def test_batch_processing_uses_local_sequential_queue(client, monkeypatch):
    template = client.post("/api/templates", json={"name": "Intake"}).json()
    client.post(f"/api/templates/{template['id']}/questions", json={"question_number": 1, "question_text": "Name", "display_order": 0, "region_x": .1, "region_y": .2, "region_width": .5, "region_height": .2})
    sample = BytesIO(); Image.new("RGB", (32, 32), "white").save(sample, format="PNG")
    client.post(f"/api/templates/{template['id']}/sample", files={"file": ("blank.png", sample.getvalue(), "image/png")})
    batch = client.post("/api/batches", data={"batch_name": "Queue test", "template_id": template["id"]}).json()
    scheduled = []
    monkeypatch.setattr("app.api.documents.processing_queue.submit", lambda batch_id: scheduled.append(batch_id) or True)
    empty = client.post(f"/api/batches/{batch['id']}/process")
    assert empty.status_code == 409
    assert not scheduled
    image_bytes = BytesIO()
    Image.new("RGB", (32, 32), "white").save(image_bytes, format="PNG")
    uploaded = client.post("/api/documents/upload", data={"batch_id": batch["id"]}, files={"files": ("form.png", image_bytes.getvalue(), "image/png")})
    assert uploaded.status_code == 201
    response = client.post(f"/api/batches/{batch['id']}/process")
    assert response.status_code == 202
    assert scheduled == [batch["id"]]
    assert client.get("/api/batches").json()[0]["name"] == "Queue test"


def test_export_uses_dynamic_questions_in_template_sheet(client):
    template = client.post("/api/templates", json={"name": "Wellbeing questionnaire"}).json()
    client.post(f"/api/templates/{template['id']}/questions", json={"question_number": 1, "question_text": "What makes you happy?", "display_order": 0})
    response = client.post("/api/export", json={"template_ids": [template["id"]]})
    assert response.status_code == 200
    workbook = load_workbook(BytesIO(response.content), read_only=True)
    assert "Wellbeing questionnaire" in workbook.sheetnames
    assert workbook.active.cell(1, 6).value == "Q1: What makes you happy?"


def test_records_corrections_filters_verification_and_export(client):
    template = client.post("/api/templates", json={"name": "Student survey"}).json()
    question = client.post(f"/api/templates/{template['id']}/questions", json={"question_number": 1, "question_text": "Favorite activity", "display_order": 0}).json()
    batch_id, document_id, record_id, answer_id = (str(uuid4()) for _ in range(4))
    with client.app.state.test_session_factory.begin() as db:
        db.add(Batch(id=batch_id, batch_name="Winter intake", template_id=template["id"], total_documents=1, processed_documents=1))
        db.add(Document(id=document_id, batch_id=batch_id, original_filename="form.png", stored_path="local_data/documents/form.png", file_hash="b" * 64, status="pending_review", page_count=1))
        db.add(StudentRecord(id=record_id, document_id=document_id, template_id=template["id"], verification_status="pending"))
        db.add(Answer(id=answer_id, student_record_id=record_id, question_id=question["id"], page_number=1, raw_ocr_text="Cricket", normalized_ocr_text="Cricket", verification_status="needs_review"))
    assert client.delete(f"/api/templates/questions/{question['id']}").status_code == 409
    filtered = client.get("/api/records", params={"q": "form.png", "status": "pending"})
    assert filtered.status_code == 200
    assert [row["id"] for row in filtered.json()] == [record_id]
    updated = client.put(f"/api/records/{record_id}", json={"student_name": "Alex Example", "student_identifier": "S-14"})
    assert updated.json()["student_name"] == "Alex Example"
    correction = client.put(f"/api/answers/{answer_id}", json={"corrected_text": "Playing cricket", "verification_status": "verified"})
    assert correction.json()["corrected_text"] == "Playing cricket"
    verified = client.post(f"/api/records/{record_id}/verify")
    assert verified.json()["verification_status"] == "verified"
    workbook_response = client.post("/api/export", json={"template_ids": [template["id"]], "batch_id": batch_id, "verified_only": True})
    assert workbook_response.status_code == 200
    workbook = load_workbook(BytesIO(workbook_response.content), read_only=True)
    sheet = workbook["Student survey"]
    assert sheet.cell(2, 2).value == "Alex Example"
    assert sheet.cell(2, 6).value == "Playing cricket"


def test_local_backup_contains_database_and_user_files(client, tmp_path, monkeypatch):
    database_path = tmp_path / "local_data" / "database" / "student_form_digitizer.db"
    database_path.parent.mkdir(parents=True)
    with sqlite3.connect(database_path) as db:
        db.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY)")
        db.execute("INSERT INTO sample VALUES (1)")
    document = tmp_path / "local_data" / "documents" / "form.png"
    document.parent.mkdir(parents=True)
    document.write_bytes(b"local form bytes")
    monkeypatch.setattr("app.api.settings.DATABASE_PATH", database_path)
    response = client.post("/api/settings/backup")
    assert response.status_code == 200
    archive_path = next((tmp_path / "local_data" / "backups").glob("*.zip"))
    with zipfile.ZipFile(archive_path) as archive:
        assert "database/student_form_digitizer.db" in archive.namelist()
        assert "documents/form.png" in archive.namelist()
        assert "BACKUP_INFO.txt" in archive.namelist()


def test_batch_worker_passes_one_provider_to_each_document(client, monkeypatch):
    template = client.post("/api/templates", json={"name": "Worker test"}).json()
    batch_id, first_id, second_id = (str(uuid4()) for _ in range(3))
    factory = client.app.state.test_session_factory
    with factory.begin() as db:
        db.add(Batch(id=batch_id, batch_name="Sequential batch", template_id=template["id"], total_documents=2))
        for document_id, suffix in ((first_id, "c"), (second_id, "d")):
            db.add(Document(id=document_id, batch_id=batch_id, original_filename=f"{suffix}.png", stored_path=f"{suffix}.png", file_hash=suffix * 64, status="uploaded", page_count=1))
    from app.services import document_processing
    provider = object()
    calls = []
    monkeypatch.setattr(document_processing, "SessionLocal", factory)
    monkeypatch.setattr(document_processing, "get_provider", lambda: provider)
    def fake_process_document(document_id, supplied):
        calls.append((document_id, supplied))
        with factory.begin() as db:
            db.get(Document, document_id).status = "pending_review"
            document_processing.refresh_batch_counts(db, batch_id)
    monkeypatch.setattr(document_processing, "process_document", fake_process_document)
    document_processing.process_batch(batch_id)
    assert {document_id for document_id, _ in calls} == {first_id, second_id}
    assert all(supplied is provider for _, supplied in calls)
    with factory() as db:
        assert db.get(Batch, batch_id).processed_documents == 2


def test_interrupted_processing_documents_are_restored_to_queue(client, monkeypatch):
    template = client.post("/api/templates", json={"name": "Recovery test"}).json()
    batch_id, document_id = str(uuid4()), str(uuid4())
    factory = client.app.state.test_session_factory
    with factory.begin() as db:
        db.add(Batch(id=batch_id, batch_name="Restart recovery", template_id=template["id"], total_documents=1))
        db.add(Document(id=document_id, batch_id=batch_id, original_filename="interrupted.png", stored_path="interrupted.png", file_hash="e" * 64, status="processing", page_count=1))
    from app.services import processing_queue as queue_module
    from app.services.processing_queue import ProcessingQueue
    queue = ProcessingQueue()
    queued = []
    monkeypatch.setattr(queue_module, "SessionLocal", factory)
    monkeypatch.setattr(queue, "submit", lambda selected_batch: queued.append(selected_batch))
    queue.restore_after_restart()
    with factory() as db:
        assert db.get(Document, document_id).status == "queued"
    assert queued == [batch_id]
