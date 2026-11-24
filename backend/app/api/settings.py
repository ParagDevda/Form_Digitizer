"""Local-only workspace backup actions."""

from datetime import datetime
from pathlib import Path
import sqlite3
import zipfile

from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.database import DATABASE_PATH, PROJECT_ROOT

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.post("/backup")
def create_backup():
    backup_dir = PROJECT_ROOT / "local_data" / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    archive_path = backup_dir / f"student-form-backup-{stamp}.zip"
    snapshot_path = backup_dir / f".database-{stamp}.sqlite"
    database_path = Path(DATABASE_PATH)
    if database_path.is_file():
        source = sqlite3.connect(database_path)
        destination = sqlite3.connect(snapshot_path)
        try:
            source.backup(destination)
        finally:
            destination.close()
            source.close()
    try:
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=4) as archive:
            if snapshot_path.is_file():
                archive.write(snapshot_path, "database/student_form_digitizer.db")
            for folder in ("documents", "templates", "processed", "exports"):
                root = PROJECT_ROOT / "local_data" / folder
                if not root.exists():
                    continue
                for path in root.rglob("*"):
                    if path.is_file() and not path.name.startswith("."):
                        archive.write(path, path.relative_to(PROJECT_ROOT / "local_data").as_posix())
            archive.writestr("BACKUP_INFO.txt", f"Created locally on {datetime.now().astimezone().isoformat()}\nOCR model files are stored separately and are not included.\n")
    except Exception:
        archive_path.unlink(missing_ok=True)
        raise
    finally:
        snapshot_path.unlink(missing_ok=True)
    return FileResponse(archive_path, filename=archive_path.name, media_type="application/zip")
