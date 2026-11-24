"""Single-worker persistent queue for CPU OCR batch jobs."""

from queue import Queue
import logging
from threading import Lock, Thread

from sqlalchemy import select, update

from app.database import SessionLocal
from app.models import Document
from app.services.document_processing import process_batch

logger = logging.getLogger(__name__)


class ProcessingQueue:
    def __init__(self) -> None:
        self._jobs: Queue[str | None] = Queue()
        self._lock = Lock()
        self._queued: set[str] = set()
        self._thread: Thread | None = None

    def start(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._thread = Thread(target=self._run, name="student-form-ocr", daemon=True)
            self._thread.start()

    def submit(self, batch_id: str) -> bool:
        self.start()
        with self._lock:
            if batch_id in self._queued:
                return False
            self._queued.add(batch_id)
            self._jobs.put(batch_id)
            return True

    def restore_after_restart(self) -> None:
        """Re-queue interrupted documents after status changes are persisted."""
        with SessionLocal.begin() as db:
            db.execute(update(Document).where(Document.status == "processing").values(status="queued", error_message="Processing was interrupted; queued to resume after restart."))
            batch_ids = db.scalars(select(Document.batch_id).where(Document.status == "queued").distinct()).all()
        for batch_id in batch_ids:
            self.submit(batch_id)

    def stop(self) -> None:
        with self._lock:
            if not self._thread or not self._thread.is_alive():
                return
            self._jobs.put(None)

    def _run(self) -> None:
        while True:
            batch_id = self._jobs.get()
            if batch_id is None:
                self._jobs.task_done()
                return
            try:
                process_batch(batch_id)
            except Exception:
                logger.exception("Unhandled batch worker failure for %s", batch_id)
                with SessionLocal.begin() as db:
                    db.execute(update(Document).where(Document.batch_id == batch_id, Document.status.in_(["processing", "queued"])).values(status="failed", error_message="The batch worker stopped unexpectedly. Retry this batch."))
            finally:
                with self._lock:
                    with SessionLocal() as db:
                        has_new_work = db.scalar(select(Document.id).where(Document.batch_id == batch_id, Document.status.in_(["uploaded", "queued"])).limit(1)) is not None
                    if has_new_work and self._thread and self._thread.is_alive():
                        self._jobs.put(batch_id)
                    else:
                        self._queued.discard(batch_id)
                self._jobs.task_done()


processing_queue = ProcessingQueue()
