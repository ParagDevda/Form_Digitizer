# Student Form Digitizer

Offline-first local application for digitizing student forms. Phase 1 establishes the React/Vite frontend, FastAPI backend, local SQLite database, and Windows startup scripts. OCR and form-processing features are intentionally not part of this phase.

## Requirements

- Windows 11, 64-bit
- Python 3.11 or newer (the current environment uses Python 3.12)
- Node.js 20.19+ or 22.12+ and npm
- Git (optional for running the app)

## First-time setup

From the project directory, create a virtual environment and install backend dependencies:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
```

Install frontend dependencies:

```powershell
cd frontend
npm install
cd ..
```

These steps need internet access for initial package installation. Runtime processing is local.

## Run

Double-click `start_app.bat`, or run it from PowerShell. It starts the API at <http://127.0.0.1:8000>, the frontend at <http://localhost:5173>, and opens the frontend in your default browser. API docs are at <http://127.0.0.1:8000/docs>.

To stop the services started by the script, run `stop_app.bat`. The script records only its own process IDs and does not terminate other Python or Node processes.

For development, the backend can be started with `python backend\run.py` after activating the virtual environment. Start the frontend with `cd frontend; npm run dev`.

## Local data

SQLite is created on first backend startup at `local_data/database/student_form_digitizer.db`. User data, uploaded documents, exports, and downloaded models are excluded from Git.

## Phase 1 status

- React + TypeScript + Vite frontend scaffold
- FastAPI API with `/api/health` and interactive API docs
- SQLite engine and initialization
- CORS configured for the local Vite development server
- Windows startup and shutdown scripts

OCR, templates, uploads, verification, and exports are future phases.
