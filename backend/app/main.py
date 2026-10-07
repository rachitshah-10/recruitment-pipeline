from contextlib import asynccontextmanager
from datetime import date
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app import models  # noqa: F401
from app.analytics import build_cohort, build_deployment, build_executive, build_recruitment
from app.database import Base, engine, get_db
from app.seed import seed_if_empty


@asynccontextmanager
async def lifespan(_app):
    Base.metadata.create_all(bind=engine)
    seed_if_empty()
    yield


app = FastAPI(title="Momentuum Blue Operations", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _day(value: Optional[str]) -> date:
    if not value:
        return date.today()
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=400, detail="Date must be YYYY-MM-DD")


def _week(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=400, detail="week must be YYYY-MM-DD")


@app.get("/api/health")
def health_check():
    return {"status": "ok", "message": "Recruitment Pipeline Backend is running"}


@app.get("/api/executive")
def executive(week: Optional[str] = None, as_of: Optional[str] = None, db: Session = Depends(get_db)):
    return build_executive(db, _day(as_of), _week(week))


@app.get("/api/recruitment")
def recruitment(week: Optional[str] = None, as_of: Optional[str] = None, db: Session = Depends(get_db)):
    return build_recruitment(db, _week(week), _day(as_of))


@app.get("/api/deployment")
def deployment(as_of: Optional[str] = None, db: Session = Depends(get_db)):
    return build_deployment(db, _day(as_of))


@app.get("/api/cohort")
def cohort(as_of: Optional[str] = None, db: Session = Depends(get_db)):
    return build_cohort(db, _day(as_of))
