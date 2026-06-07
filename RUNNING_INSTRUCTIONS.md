# Running ScrapGPT (Local Development)

This guide explains how to run the ScrapGPT backend and frontend servers locally on Windows.

---

## 1. Backend Server (FastAPI)

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
