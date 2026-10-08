from contextlib import asynccontextmanager
from datetime import date
from typing import Optional

from fastapi import Body, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.matching import MatchRequest, match_bench
from app import models  # noqa: F401
from app.academy import build_academy, ensure_academy, resume_file
from app.analytics import build_cohort, build_deployment, build_executive, build_recruitment
from app.chatbot import reply as chat_reply
from app.cost_seed import ensure_cost_rates
from app.database import Base, engine, get_db
from app.economics import PHASES, Filters, build_economics, save_rates
from app.recommendations import build_actions, set_status
from app.seed import seed_if_empty
from app.ai_requirements import RequirementInput, extract_requirements


@asynccontextmanager
async def lifespan(_app):
    Base.metadata.create_all(bind=engine)
    seed_if_empty()
    ensure_cost_rates()
    ensure_academy()
    yield


app = FastAPI(title="Momentuum Blue Operations", version="0.3.0", lifespan=lifespan)

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


def _filters(
    start: Optional[str] = None,
    end: Optional[str] = None,
    phase: Optional[str] = None,
    role: Optional[str] = None,
    location: Optional[str] = None,
    cohort: Optional[str] = None,
    basis: Optional[str] = None,
) -> Filters:
    if phase and phase not in PHASES:
        raise HTTPException(status_code=400, detail="phase must be one of {}".format(", ".join(PHASES)))
    if basis and basis not in ("inferred", "reported"):
        raise HTTPException(status_code=400, detail="basis must be inferred or reported")
    filters = Filters(
        start=_week(start),
        end=_day(end),
        phase=phase or None,
        role=role or None,
        location=location or None,
        cohort=cohort or None,
        basis=basis or "inferred",
    )
    if filters.start and filters.start > filters.end:
        raise HTTPException(status_code=400, detail="start must be on or before end")
    return filters


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

@app.post("/api/deployment/match")
def deployment_match(
    payload: MatchRequest,
    as_of: Optional[str] = None,
    db: Session = Depends(get_db)
):
    try:
        return match_bench(
            db=db,
            as_of=_day(as_of),
            request=payload
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc)
        )

@app.get("/api/cohort")
def cohort(as_of: Optional[str] = None, db: Session = Depends(get_db)):
    return build_cohort(db, _day(as_of))


@app.get("/api/academy")
def academy(cohort: Optional[str] = None, as_of: Optional[str] = None, db: Session = Depends(get_db)):
    return build_academy(db, _day(as_of), cohort)


@app.get("/api/academy/resumes/{trainee_id}")
def academy_resume(trainee_id: int, db: Session = Depends(get_db)):
    found = resume_file(db, trainee_id)
    if found is None:
        raise HTTPException(status_code=404, detail="No resume for that candidate")
    filename, body = found
    return Response(
        content=body,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="{}"'.format(filename)},
    )


@app.get("/api/economics")
def economics(filters: Filters = Depends(_filters), db: Session = Depends(get_db)):
    return build_economics(db, filters)


@app.put("/api/economics/rates")
def economics_rates(payload: dict = Body(...), db: Session = Depends(get_db)):
    try:
        save_rates(db, payload.get("rates") or [])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True}


@app.get("/api/actions")
def actions(filters: Filters = Depends(_filters), db: Session = Depends(get_db)):
    return build_actions(db, filters)


@app.post("/api/chat")
def chat(payload: dict = Body(...), as_of: Optional[str] = None, db: Session = Depends(get_db)):
    return chat_reply(db, str(payload.get("message") or ""), _day(as_of))


@app.post("/api/actions/{rec_id}/status")
def action_status(rec_id: str, payload: dict = Body(...), db: Session = Depends(get_db)):
    try:
        return set_status(db, rec_id, payload.get("status"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@app.post("/api/deployment/extract-requirements")
def deployment_extract_requirements(payload: RequirementInput):
    try:
        result = extract_requirements(payload.description)
        return result

    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc)
        )
