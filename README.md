# Recruitment Pipeline Full-Stack Application

A full-stack web application starter with a FastAPI backend, SQLite database (SQLAlchemy ORM), and React + Vite + Tailwind CSS frontend.

## Environment Overview

- **OS / Architecture:** macOS (Apple Silicon arm64)
- **Node.js:** v24.10.0 (Installed into `backend/venv` via `nodeenv`)
- **Package Manager:** npm v11.6.1
- **Python:** Python 3.9 (Virtual environment at `backend/venv`)
- **Backend:** FastAPI + Uvicorn + SQLAlchemy
- **Database:** SQLite (embedded via Python standard library)
- **Frontend:** React 19 + Vite + Tailwind CSS + Lucide Icons

---

## Project Structure

```text
recruitment_pipeline/
├── MB_Master_Dashboard_AB_V2.xlsx   # Source workbook; seeded on first startup
├── backend/
│   ├── app/
│   │   ├── main.py        # API routes
│   │   ├── models.py      # pipeline_weeks, training_weeks, people
│   │   ├── seed.py        # Loads the workbook into SQLite
│   │   ├── analytics.py   # Executive, funnel, deployment, cohort metrics
│   │   ├── config.py      # Thresholds, risk levels, and score weights for Economics / Actions
│   │   ├── economics.py   # Resource burn, hiring economics, revenue at risk (calculated metrics)
│   │   ├── recommendations.py  # Deterministic rule engine + scoring for Leadership Actions
│   │   ├── cost_seed.py   # Seeds resource_rates (assumptions) and demand_forecast (demo)
│   │   └── database.py    # SQLite engine and session configuration
│   ├── requirements.txt
│   └── venv/
├── frontend/
│   └── src/               # Executive, recruitment, deployment, cohort screens
└── .gitignore
```

The API creates those three tables on startup and fills them from the workbook when the database is empty.

---

## Setup (One Time)

Node.js and npm are installed into the Python virtual environment with `nodeenv`, so activating the venv gives you `python`, `node`, and `npm` for this project.

```bash
# From the project root
python3 -m venv backend/venv
source backend/venv/bin/activate
pip install -r backend/requirements.txt nodeenv
nodeenv -p --node=24.10.0 --prebuilt
cd frontend && npm install
```

## How to Run

Activate the venv in each terminal first: `source backend/venv/bin/activate`

### 1. Run the Backend Server
```bash
# From the project root
uvicorn app.main:app --app-dir backend --reload --reload-dir backend/app --port 8000
```
- API Health Check: `http://localhost:8000/api/health`
- Interactive Swagger API Docs: `http://localhost:8000/docs`

### 2. Run the Frontend Development Server
```bash
cd frontend
npm run dev
```
- Web Application: `http://localhost:3000`
- API calls to `/api/*` are automatically proxied to the backend at port 8000.
