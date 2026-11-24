# Student Form Digitizer

Student Form Digitizer is a Windows-first local application for mapping handwritten questionnaire answers into verified student records and Excel workbooks. The API, SQLite database, uploaded documents, processed pages, exports, and OCR model are stored on this computer.

## Requirements

- Windows 11, 64-bit
- Python 3.11+ (the development environment uses Python 3.12)
- Node.js 20.19+ or 22.12+ and npm
- Internet access for initial package/model setup only
- CPU-only OCR; no CUDA or NVIDIA GPU required

## First-time setup

Run these commands from the project directory:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements-dev.txt
cd frontend
npm install
cd ..
```

### Install the local OCR model (one time)

The PyTorch wheel is CPU-only. These commands download packages and the pretrained English handwriting model; normal application startup and inference do not download models.

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-ocr.txt
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-ocr-hf.txt
.\.venv\Scripts\python.exe scripts\download_trocr_model.py
```

Model files are stored in `backend/models/trocr-base-handwritten/` and are excluded from Git. Keep that directory on the machine for offline OCR use. Runtime model loading is configured for local files only.

## Run the application

Double-click `start_app.bat`. It starts FastAPI at <http://127.0.0.1:8000>, the Vite UI at <http://localhost:5173>, and opens the UI in the default browser. API documentation is at <http://127.0.0.1:8000/docs>.

Run `stop_app.bat` to stop only the processes started by the startup script. Logs are written under `.run-state/logs/` while the app runs.

If the default ports are already in use, start with alternate local ports from PowerShell, for example `powershell -ExecutionPolicy Bypass -File scripts\start_app.ps1 -ApiPort 8002 -FrontendPort 5175`. The frontend proxy follows the selected API port. Stop those services with `scripts\stop_app.ps1`.

The application workflow is: create a template, add questions, upload a blank sample for each page, and draw normalized answer regions; create a named batch and upload forms; start the batch for sequential local OCR; review every answer against the original page; then export all or verified records, optionally filtered by batch. Failed documents can be retried from the Upload page. Blank answer regions are not sent to OCR, and failed alignment is reported instead of silently reading the wrong area.

For manual development startup, open two PowerShell terminals from the project folder.

Terminal 1, backend API:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Terminal 2, frontend:

```powershell
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

Open <http://localhost:5173>; stop each development server with `Ctrl+C`. The API docs are at <http://127.0.0.1:8000/docs>. `start_app.bat` and `stop_app.bat` are the one-click alternatives.

## Data locations

- SQLite database: `local_data/database/student_form_digitizer.db`
- Original uploads: `local_data/documents/`
- Template samples: `local_data/templates/`
- Processed page and answer crops: `local_data/processed/`
- Excel exports: `local_data/exports/`
- OCR model: `backend/models/`

SQLite schema changes are managed with Alembic. To apply pending migrations manually:

```powershell
.\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini upgrade head
```

Back up the database and local data folders together. These paths are excluded from Git.

The Settings page creates a ZIP backup containing a consistent SQLite snapshot plus originals, template samples, processed files, and exports. The app stores a local copy under `local_data/backups/` and downloads the archive through the browser. The model weights and benchmark dataset are stored separately and are not included.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests -q
cd frontend
npm run build
```

The model-backed document-processing integration test uses a generated form and a local provider; run it explicitly with `python -m pytest backend\tests -m integration -q` after the TrOCR weights are installed. The public IAM-line benchmark is the measured handwriting reference set; this workspace does not contain representative student form ground truth, so the benchmark does not predict accuracy on your particular forms. Every OCR result remains pending review until a person verifies it.

## OCR benchmark

The benchmark utility compares predictions with ground-truth transcriptions and reports measured CER, WER, and processing time. To prepare a 50-line English handwriting sample from the IAM-line test split, install the benchmark helper and run:

```powershell
python -m pip install -r backend\requirements-benchmark.txt
python scripts\prepare_iam_benchmark.py --samples 50
.\.venv\Scripts\python.exe scripts\benchmark_ocr.py local_data\benchmark\iam-line-test\ground-truth.csv
```

The prepared CSV is at `local_data/benchmark/iam-line-test/ground-truth.csv`; substitute that path in the benchmark command. The data is a public English handwritten text set with transcriptions; its dataset card declares MIT. The benchmark subset is stored locally and excluded from Git. This dataset tests line recognition, not camera-captured student forms, so it does not replace evaluation on the intended forms. [IAM-line dataset card](https://huggingface.co/datasets/ianua/IAM-line).

The runner reports sample count, CER, WER, processing time, and peak process RSS. Use `--limit 10` for a short smoke run. The measured subset result and its limitations are in [docs/ocr-benchmark.md](docs/ocr-benchmark.md). Do not add student forms or private datasets to Git.
