"""
Evaluation endpoint.

POST /api/v1/evaluation/run
    Runs evaluation for a developer and returns metrics.

GET /api/v1/evaluation/report
    Returns the latest evaluation report.
"""

from datetime import datetime

import structlog
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text

from app.db.session import AsyncSessionLocal
from app.services.ml.evaluator import Evaluator
from app.services.ml.gap_modeler import GapModeler
from app.services.ml.recommender import Recommender
from app.services.ml.skill_graph import SkillGraphBuilder

logger = structlog.get_logger()
router = APIRouter()

builder = SkillGraphBuilder()
modeler = GapModeler()
recommender = Recommender()
evaluator = Evaluator()


# ── Response schemas ──────────────────────────────────────────────────────────

class EvaluationResultOut(BaseModel):
    username: str
    goal_domain: str
    recommended_repos: list[str]
    actual_contributions: list[str]
    hits: list[str]
    precision_at_5: float
    reciprocal_rank: float
    baseline_precision: float
    improvement_over_baseline: float


class EvaluationSummaryOut(BaseModel):
    total_developers: int
    mean_precision_at_5: float
    mean_reciprocal_rank: float
    coverage: float
    baseline_mean_precision: float
    mean_improvement: float
    results: list[EvaluationResultOut]
    generated_at: datetime
    interpretation: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/run", response_model=EvaluationResultOut)
async def run_evaluation(
    username: str = Query(...),
    goal: str = Query(...),
):
    """
    Run evaluation for a single developer.

    Fetches their real recent contributions and compares against
    what our system would have recommended.
    """
    log = logger.bind(username=username, goal=goal)
    log.info("Running evaluation")

    # ── Load developer ────────────────────────────────────────────────────
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("SELECT id FROM developers WHERE github_username = :u"),
            {"u": username},
        )
        developer = result.fetchone()

    if not developer:
        raise HTTPException(
            status_code=404,
            detail=f"Developer '{username}' not found. Analyze first.",
        )

    developer_id = str(developer.id)

    # ── Load skills ───────────────────────────────────────────────────────
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("""
                SELECT skill_key, category, confidence, evidence_count
                FROM skill_nodes WHERE developer_id = :id
            """),
            {"id": developer_id},
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

    # ── Generate recommendations ──────────────────────────────────────────
    skill_graph = builder.build(developer_id, username, skill_rows)

    try:
        gap_vector = modeler.compute(skill_graph, goal)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    rec_result = recommender.recommend(gap_vector, top_k=5)
    recommended_repos = [r.full_name for r in rec_result.recommendations]

    # ── Baseline: top repos by stars in domain ────────────────────────────
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("""
                SELECT full_name FROM repositories
                ORDER BY stars DESC LIMIT 5
            """),
        )
        baseline_repos = [row.full_name for row in result.fetchall()]

    # ── Fetch real contributions ──────────────────────────────────────────
    actual = evaluator.fetch_recent_contributions(username, days_back=90)

    # ── Evaluate ──────────────────────────────────────────────────────────
    eval_result = evaluator.evaluate_single(
        username=username,
        goal_domain=goal,
        recommended_repos=recommended_repos,
        actual_contributions=actual,
        baseline_repos=baseline_repos,
        k=5,
    )

    log.info(
        "Evaluation complete",
        precision=eval_result.precision_at_k,
        mrr=eval_result.reciprocal_rank,
    )

    return EvaluationResultOut(
        username=username,
        goal_domain=goal,
        recommended_repos=eval_result.recommended_repos,
        actual_contributions=eval_result.actual_contributions,
        hits=eval_result.hits,
        precision_at_5=eval_result.precision_at_k,
        reciprocal_rank=eval_result.reciprocal_rank,
        baseline_precision=eval_result.baseline_precision,
        improvement_over_baseline=eval_result.improvement_over_baseline,
    )


@router.get("/interpret")
async def interpret_metrics():
    """
    Returns an explanation of the evaluation metrics.
    Useful for portfolio documentation.
    """
    return {
        "metrics": {
            "precision_at_5": {
                "definition": "Of the top 5 recommended repos, what fraction did the developer actually contribute to?",
                "range": "0.0 to 1.0",
                "interpretation": "0.2 means 1 out of 5 recommendations led to a real contribution",
            },
            "mean_reciprocal_rank": {
                "definition": "Where in the ranking was the first successful recommendation?",
                "range": "0.0 to 1.0",
                "interpretation": "1.0 = first recommendation was perfect. 0.5 = second recommendation was the hit.",
            },
            "coverage": {
                "definition": "What percentage of developers got at least one successful recommendation?",
                "range": "0.0 to 1.0",
                "interpretation": "0.7 means 70% of developers found at least one relevant repo",
            },
            "improvement_over_baseline": {
                "definition": "How much better are our recommendations vs. just showing popular repos?",
                "range": "Negative to positive",
                "interpretation": "+0.1 means 10 percentage points better than showing most-starred repos",
            },
        },
        "baselines": {
            "star_count": "Recommend the most-starred repos in the target domain",
            "language_match": "Recommend repos in the developer's primary language",
            "good_first_issue": "Recommend repos with good-first-issue labels",
        },
        "note": "Evaluation runs retrospectively — we check if recommendations match repos the developer actually contributed to after analysis.",
    }