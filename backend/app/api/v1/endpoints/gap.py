"""
Gap analysis endpoint.

GET /api/v1/gap/{username}?goal={domain}
    Returns the gap between a developer's skills and a goal domain.
"""

from datetime import datetime

import structlog
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text

from app.core.config import settings
from app.services.ml.gap_modeler import GapModeler
from app.services.ml.skill_graph import SkillGraphBuilder
from app.services.ml.target_profiles import list_domains

logger = structlog.get_logger()
router = APIRouter()

from app.db.session import AsyncSessionLocal, execute_query

builder = SkillGraphBuilder()
modeler = GapModeler()


# ── Response schemas ──────────────────────────────────────────────────────────

class SkillGapOut(BaseModel):
    skill_key: str
    category: str
    required_confidence: float
    current_confidence: float
    gap_size: float
    priority: str


class GapVectorOut(BaseModel):
    developer_id: str
    github_username: str
    goal_domain: str
    goal_display_name: str
    readiness_score: float
    top_priorities: list[str]
    gaps: list[SkillGapOut]
    satisfied: list[SkillGapOut]
    computed_at: datetime
    message: str


class DomainOut(BaseModel):
    domain: str
    display_name: str
    description: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/domains", response_model=list[DomainOut])
async def get_domains():
    """List all available goal domains."""
    return list_domains()


@router.get("/{username}", response_model=GapVectorOut)
async def get_gap(
    username: str,
    goal: str = Query(
        ...,
        description="Goal domain key e.g. 'ai-ml-tooling', 'web-frontend'",
    ),
):
    """
    Compute the skill gap between a developer and a goal domain.

    The developer must have been analyzed first via /analyze/{username}.
    Returns a prioritized list of skills to develop.
    """
    log = logger.bind(username=username, goal=goal)
    log.info("Gap analysis requested")

    # ── Load developer from DB ────────────────────────────────────────────
    from app.db.session import execute_query
    rows = execute_query(
        "SELECT id, github_username FROM developers WHERE github_username = %(username)s",
        {"username": username}
    )
    developer = rows[0] if rows else None

    if not developer:
        raise HTTPException(
            status_code=404,
            detail=f"Developer '{username}' not found. "
                   f"Please analyze them first via /analyze/{username}",
        )

    developer_id = str(developer["id"])

    # ── Load skill nodes from DB ──────────────────────────────────────────
    skill_rows_raw = execute_query(
        "SELECT skill_key, category, confidence, evidence_count FROM skill_nodes WHERE developer_id = %(developer_id)s",
        {"developer_id": developer_id}
    )

    skill_rows = [
        {
            "skill_key": row.skill_key,
            "category": row.category,
            "confidence": float(row.confidence),
            "evidence_count": row.evidence_count,
        }
        for row in rows
    ]

    # ── Build skill graph ─────────────────────────────────────────────────
    skill_graph = builder.build(developer_id, username, skill_rows)

    # ── Compute gap ───────────────────────────────────────────────────────
    try:
        gap_vector = modeler.compute(skill_graph, goal)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # ── Generate human-readable message ──────────────────────────────────
    message = _generate_message(gap_vector)

    log.info(
        "Gap analysis complete",
        readiness=gap_vector.readiness_score,
        gaps=len(gap_vector.gaps),
    )

    return GapVectorOut(
        developer_id=developer_id,
        github_username=username,
        goal_domain=gap_vector.goal_domain,
        goal_display_name=gap_vector.goal_display_name,
        readiness_score=gap_vector.readiness_score,
        top_priorities=gap_vector.top_priorities,
        gaps=[
            SkillGapOut(
                skill_key=g.skill_key,
                category=g.category,
                required_confidence=g.required_confidence,
                current_confidence=g.current_confidence,
                gap_size=g.gap_size,
                priority=g.priority,
            )
            for g in gap_vector.gaps
        ],
        satisfied=[
            SkillGapOut(
                skill_key=s.skill_key,
                category=s.category,
                required_confidence=s.required_confidence,
                current_confidence=s.current_confidence,
                gap_size=s.gap_size,
                priority=s.priority,
            )
            for s in gap_vector.satisfied
        ],
        computed_at=gap_vector.computed_at,
        message=message,
    )


def _generate_message(gap_vector) -> str:
    """Generate a human-readable summary of the gap analysis."""
    readiness = gap_vector.readiness_score
    goal = gap_vector.goal_display_name
    gap_count = len(gap_vector.gaps)
    satisfied_count = len(gap_vector.satisfied)

    if readiness >= 0.8:
        return (
            f"You're well prepared for {goal} contributions! "
            f"You satisfy {satisfied_count} of the key requirements. "
            f"Focus on {gap_vector.top_priorities[0] if gap_vector.top_priorities else 'stretch goals'} "
            f"to become an even stronger contributor."
        )
    elif readiness >= 0.5:
        priorities = ", ".join(gap_vector.top_priorities[:2])
        return (
            f"You're on your way to {goal} contributions. "
            f"You already meet {satisfied_count} requirements. "
            f"Focus on building: {priorities}."
        )
    else:
        priorities = ", ".join(gap_vector.top_priorities[:3])
        return (
            f"You have {gap_count} skill gaps to close for {goal}. "
            f"Start with: {priorities}. "
            f"These are the highest-impact skills to develop first."
        )