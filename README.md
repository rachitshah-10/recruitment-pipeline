# Recruitment Pipeline Full-Stack Application

A full-stack web application starter with a FastAPI backend, SQLite database (SQLAlchemy ORM), and React + Vite + Tailwind CSS frontend.

## Environment Overview

- **OS / Architecture:** macOS (Apple Silicon arm64)
- **Node.js:** v24.21.0 (Managed via `nvm`)
- **Package Manager:** npm v11.19.0
- **Python:** Python 3.9 (Virtual environment at `backend/venv`)
- **Backend:** FastAPI + Uvicorn + SQLAlchemy
- **Database:** SQLite (embedded via Python standard library)
- **Frontend:** React 19 + Vite + Tailwind CSS + Lucide Icons

---

## Project Structure

```text
recruitment_pipeline/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py        # FastAPI health check and starter routes
│   │   └── database.py    # SQLite engine and session configuration
│   ├── requirements.txt   # Python dependencies
│   └── venv/              # Python virtual environment
├── frontend/
│   ├── src/
│   │   ├── App.jsx        # Starter React dashboard
│   │   ├── index.css      # Tailwind CSS configuration
│   │   └── main.jsx       # React application entry
│   ├── package.json       # Frontend dependencies and scripts
│   └── vite.config.js     # Vite configuration with API proxy
└── .gitignore
```

---

## How to Run (When Ready)

### 1. Run the Backend Server
```bash
# From the project root
./backend/venv/bin/uvicorn app.main:app --app-dir backend --reload --port 8000
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
