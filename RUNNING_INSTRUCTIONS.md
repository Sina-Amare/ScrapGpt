# Running ScrapGPT (Local Development)

This guide explains how to run the ScrapGPT backend and frontend servers locally on Windows.

---

## Quick Start — Scripts (Recommended)

Two PowerShell scripts at the project root handle both servers with a single command.
No extra terminal windows needed — both servers run as hidden background processes.

### Start both servers

```powershell
.\dev-start.ps1
```

Output:

```text
Backend  started (PID 12345)  -> http://127.0.0.1:8000
Frontend started (PID 12346) -> http://127.0.0.1:5173
Run .\dev-stop.ps1 to stop both.
```

PIDs are saved to `.dev-pids` in the project root.

### Stop both servers

```powershell
.\dev-stop.ps1
```

This kills the processes saved in `.dev-pids` and also sweeps ports 8000 and 5173 as a
fallback (catches servers started manually).

---

## Manual Start (Two Terminals)

### 1. Backend Server (FastAPI)

Run these commands in your first terminal (at the project root directory):

### If using PowerShell:
```powershell
# 1. Set the python path to the current directory
$env:PYTHONPATH="."

# 2. Run the Uvicorn development server
.\venv\Scripts\python -m uvicorn app.main:app --reload
```

### If using Command Prompt (CMD):
```cmd
:: 1. Set the python path to the current directory
set PYTHONPATH=.

:: 2. Run the Uvicorn development server
venv\Scripts\python -m uvicorn app.main:app --reload
```

* **Backend URL:** [http://127.0.0.1:8000](http://127.0.0.1:8000)
* **API Swagger Documentation:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## 2. Frontend Server (Vite + React)

Open a **second terminal window/tab**, navigate to the `frontend` directory, and start the development server:

```powershell
# 1. Navigate to the frontend folder
cd frontend

# 2. Start the development server
npm run dev
```

* **Frontend URL:** [http://127.0.0.1:5173](http://127.0.0.1:5173)

---

## Troubleshooting & Tips

- **PostgreSQL Dependency:** Ensure your local PostgreSQL database is running, as it is required for backend readiness probes.
- **Environment Variables:** Make sure you have created your `.env` file in the root directory and configured it (copying from `.env.example`).
