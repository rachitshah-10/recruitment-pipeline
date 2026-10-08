
"""
Momentum Blue - Intelligent Bench-to-Client Matching Engine

Features:
1. Find employees currently on the bench
2. Filter by role and location
3. Compare skills with client requirements
4. Calculate explainable matching scores
5. Identify missing skills
6. Rank candidates for deployment

Note: This is a deterministic matching MVP.
LLM-generated explanations can be added later.
"""

from datetime import date

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.analytics import build_deployment


# ---------------------------------------------
# 1. CLIENT REQUIREMENT INPUT
# ---------------------------------------------

class MatchRequest(BaseModel):
    client: str = Field(
        min_length=1,
        max_length=100
    )

    role: str = "Any"
    location: str = "Any"

    required_skills: list[str] = Field(
        min_length=1
    )

    # Manually entered employee skill profiles
    # Format: {"employee_id": ["Python", "AWS"]}
    profiles: dict[str, list[str]] = Field(
        default_factory=dict
    )


# ---------------------------------------------
# 2. NORMALIZE SKILLS
# ---------------------------------------------

def normalize_skill(skill: str) -> str:
    """
    Normalize a skill for case-insensitive comparison.

    Examples:
        "Python"  -> "python"
        "PYTHON"  -> "python"
        " FastAPI " -> "fastapi"

    Also removes extra whitespace.
    """

    return " ".join(
        skill.strip().casefold().split()
    )


def normalize_skills(skills):
    """
    Remove duplicate skills without losing
    the original display capitalization.

    Comparisons are case-insensitive.

    Examples:
        ["Python", "PYTHON", "AWS"]
        -> ["Python", "AWS"]

        ["FastAPI", "fastapi", "RAG"]
        -> ["FastAPI", "RAG"]
    """

    unique_skills = {}
    
    for skill in skills:
        if not isinstance(skill, str):
            continue

        display_skill = " ".join(
            skill.strip().split()
        )

        if not display_skill:
            continue

        normalized = normalize_skill(display_skill)

        if normalized not in unique_skills:
            unique_skills[normalized] = display_skill

    return list(unique_skills.values())


# ---------------------------------------------
# 3. CALCULATE SKILL MATCH SCORE
# ---------------------------------------------

def calculate_match_score(required, employee_skills):
    """
    Calculate percentage of required skills matched.

    Matching is case-insensitive.

    The matched and missing skill lists preserve
    capitalization from the client requirements.

    Example:
        Required: ["Python", "FastAPI", "AWS", "RAG"]
        Employee: ["python", "FASTAPI", "aws"]

        Score: 75
        Matched: ["Python", "FastAPI", "AWS"]
        Missing: ["RAG"]
    """

    # Deduplicate requirements while preserving display names
    required_skills = normalize_skills(required)

    # Build normalized employee skill set
    employee_set = {
        normalize_skill(skill)
        for skill in employee_skills
        if isinstance(skill, str) and skill.strip()
    }

    matched = []
    missing = []

    for skill in required_skills:
        normalized_required = normalize_skill(skill)

        if normalized_required in employee_set:
            matched.append(skill)
        else:
            missing.append(skill)

    score = (
        round(100 * len(matched) / len(required_skills))
        if required_skills else 0
    )

    return score, matched, missing


# ---------------------------------------------
# 4. BENCH-TO-CLIENT MATCHING ENGINE
# ---------------------------------------------

def match_bench(
    db: Session,
    as_of: date,
    request: MatchRequest
):
    """
    Retrieve deployment roster and rank eligible
    bench employees against client requirements.
    """

    deployment_data = build_deployment(db, as_of)

    roster = deployment_data["roster"]

    # Only consider employees currently on bench
    bench_employees = [
        person for person in roster
        if person.get("bucket") == "On bench"
    ]

    # Normalize and deduplicate requirements
    # while preserving their original capitalization.
    required_skills = normalize_skills(
        request.required_skills
    )

    if not required_skills:
        raise ValueError(
            "At least one valid required skill must be provided."
        )

    results = []

    # -----------------------------------------
    # 5. FILTER AND SCORE EMPLOYEES
    # -----------------------------------------

    for person in bench_employees:

        employee_role = person.get("career_stage") or ""
        employee_location = person.get("location") or ""

        # Role eligibility
        if request.role.strip().casefold() != "any":
            if (
                employee_role.strip().casefold()
                != request.role.strip().casefold()
            ):
                continue

        # Location eligibility
        if request.location.strip().casefold() != "any":
            if (
                employee_location.strip().casefold()
                != request.location.strip().casefold()
            ):
                continue

        employee_id = str(person.get("id"))

        # Skill profiles are supplied explicitly.
        # Do not assume skills based on employee role.
        profile_skills = request.profiles.get(
            employee_id, []
        )

        employee_skills = normalize_skills(
            profile_skills
        )

        score, matched, missing = calculate_match_score(
            required_skills,
            employee_skills
        )

        profile_provided = bool(employee_skills)

        # -------------------------------------
        # 6. EXPLAIN MATCH RESULTS
        # -------------------------------------

        if profile_provided:
            explanation = (
                f"Matched {len(matched)} of "
                f"{len(required_skills)} required skills. "
                f"Missing skills: "
                f"{', '.join(missing) if missing else 'None'}."
            )
        else:
            explanation = (
                "No verified skill profile is available. "
                "Matching score cannot be established."
            )

        results.append({
            "id": person.get("id"),
            "name": person.get("name"),
            "role": employee_role,
            "location": employee_location,
            "score": score if profile_provided else None,
            "matched_skills": matched,
            "missing_skills": missing,
            "profile_provided": profile_provided,
            "explanation": explanation
        })

    # -----------------------------------------
    # 7. RANK CANDIDATES
    # -----------------------------------------

    results.sort(
        key=lambda employee: (
            not employee["profile_provided"],
            -(employee["score"] or 0),
            employee["name"] or ""
        )
    )

    # -----------------------------------------
    # 8. RETURN MATCHING RESULTS
    # -----------------------------------------

    return {
        "client": request.client,
        "as_of": as_of.isoformat(),
        "required_skills": required_skills,
        "bench_count": len(bench_employees),
        "eligible_count": len(results),
        "matches": results,
        "disclaimer": (
            "Recommendations are decision-support only. "
            "Skill profiles are manually supplied and "
            "must be verified before client deployment."
        )
    }
