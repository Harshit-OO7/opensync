"""
Repository guide endpoint.

GET /api/v1/guide/{username}?repo={full_name}&goal={domain}
    Returns a personalized AI explanation of a repository.
"""

import structlog
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text

from app.db.session import AsyncSessionLocal
from app.services.ml.gap_modeler import GapModeler
from app.services.ml.skill_graph import SkillGraphBuilder
from app.services.rag.repo_guide import RepoGuide

logger = structlog.get_logger()
router = APIRouter()

builder = SkillGraphBuilder()
modeler = GapModeler()
guide = RepoGuide()


# ── Response schema ───────────────────────────────────────────────────────────

class RepoGuideOut(BaseModel):
    repo_full_name: str
    github_username: str
    goal_domain: str
    summary: str
    why_good_fit: str
    how_to_start: str
    skills_they_will_learn: list[str]
    good_first_areas: list[str]
    encouragement: str


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.get("/{username}", response_model=RepoGuideOut)
async def get_repo_guide(
    username: str,
    repo: str = Query(..., description="Full repo name e.g. 'huggingface/datasets'"),
    goal: str = Query(..., description="Goal domain e.g. 'ai-ml-tooling'"),
):
    """
    Get a personalized AI explanation of a repository.

    Explains the repo in terms of the developer's specific skill gaps
    and provides concrete steps to make their first contribution.
    """
    log = logger.bind(username=username, repo=repo, goal=goal)
    log.info("Repo guide requested")

    # ── Load developer ────────────────────────────────────────────────────
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("SELECT id FROM developers WHERE github_username = :username"),
            {"username": username},
        )
        developer = result.fetchone()

    if not developer:
        raise HTTPException(
            status_code=404,
            detail=f"Developer '{username}' not found. "
                   f"Analyze them first via /analyze/{username}",
        )

    developer_id = str(developer.id)

    # ── Load skill nodes ──────────────────────────────────────────────────
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("""
                SELECT skill_key, category, confidence, evidence_count
                FROM skill_nodes WHERE developer_id = :developer_id
            """),
            {"developer_id": developer_id},
        )
        rows = result.fetchall()

    skill_rows = [
        {
            "skill_key": row.skill_key,
            "category": row.category,
            "confidence": float(row.confidence),
            "evidence_count": row.evidence_count,
        }
        for row in rows
    ]

    # ── Build skill graph + gap ───────────────────────────────────────────
    skill_graph = builder.build(developer_id, username, skill_rows)

    try:
        gap_vector = modeler.compute(skill_graph, goal)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # ── Generate guide ────────────────────────────────────────────────────
    try:
        result = guide.explain(repo, gap_vector)
    except Exception as e:
        log.error("Guide generation failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to generate repo guide.",
        )

    return RepoGuideOut(
        repo_full_name=repo,
        github_username=username,
        goal_domain=goal,
        summary=result.get("summary", ""),
        why_good_fit=result.get("why_good_fit", ""),
        how_to_start=result.get("how_to_start", ""),
        skills_they_will_learn=result.get("skills_they_will_learn", []),
        good_first_areas=result.get("good_first_areas", []),
        encouragement=result.get("encouragement", ""),
    )