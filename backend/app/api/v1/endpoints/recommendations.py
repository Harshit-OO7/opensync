"""
Recommendations endpoint.

GET /api/v1/recommendations/debug
    Debug Qdrant connection and contents.

GET /api/v1/recommendations/{username}?goal={domain}
    Returns gap-aware repository recommendations.

POST /api/v1/recommendations/index
    Triggers repository indexing (admin use).
"""

from datetime import datetime

import structlog
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text

from app.core.config import settings
from app.db.session import AsyncSessionLocal, execute_query
from app.services.ml.gap_modeler import GapModeler
from app.services.ml.recommender import Recommender
from app.services.ml.repo_indexer import RepoIndexer
from app.services.ml.skill_graph import SkillGraphBuilder

logger = structlog.get_logger()
router = APIRouter()

builder = SkillGraphBuilder()
modeler = GapModeler()
recommender = Recommender()


# ── Response schemas ──────────────────────────────────────────────────────────

class RepoRecommendationOut(BaseModel):
    full_name: str
    description: str
    language: str
    topics: list[str]
    stars: int
    newcomer_friendliness: float
    relevance_score: float
    matched_gaps: list[str]
    explanation: str


class RecommendationResultOut(BaseModel):
    github_username: str
    goal_domain: str
    goal_display_name: str
    readiness_score: float
    recommendations: list[RepoRecommendationOut]
    total_found: int
    generated_at: datetime


class IndexResultOut(BaseModel):
    message: str
    status: str


# ── Debug endpoint ────────────────────────────────────────────────────────────

@router.get("/debug")
async def debug_qdrant():
    """Debug endpoint to check Qdrant connection and contents."""
    from qdrant_client import QdrantClient

    try:
        if settings.QDRANT_API_KEY:
            client = QdrantClient(
                url=f"https://{settings.QDRANT_HOST}",
                api_key=settings.QDRANT_API_KEY,
            )
        else:
            client = QdrantClient(
                host=settings.QDRANT_HOST,
                port=settings.QDRANT_PORT,
            )

        collections = client.get_collections()
        collection_names = [c.name for c in collections.collections]

        try:
            points, _ = client.scroll(
                collection_name="repositories",
                limit=5,
                with_payload=True,
            )
            return {
                "status": "ok",
                "collections": collection_names,
                "sample_points": [p.payload for p in points],
                "total_sample": len(points),
                "qdrant_host": settings.QDRANT_HOST,
                "has_api_key": bool(settings.QDRANT_API_KEY),
            }
        except Exception as e:
            return {
                "status": "error",
                "collections": collection_names,
                "error": str(e),
                "qdrant_host": settings.QDRANT_HOST,
                "has_api_key": bool(settings.QDRANT_API_KEY),
            }
    except Exception as e:
        return {
            "status": "connection_error",
            "error": str(e),
            "qdrant_host": settings.QDRANT_HOST,
            "has_api_key": bool(settings.QDRANT_API_KEY),
        }


# ── Main endpoints ────────────────────────────────────────────────────────────

@router.get("/{username}", response_model=RecommendationResultOut)
async def get_recommendations(
    username: str,
    goal: str = Query(
        ...,
        description="Goal domain e.g. 'ai-ml-tooling', 'web-frontend'",
    ),
    top_k: int = Query(5, ge=1, le=10),
):
    """
    Get gap-aware repository recommendations for a developer.

    The developer must be analyzed first via /analyze/{username}.
    Returns repositories ranked by how well they address skill gaps.
    """
    log = logger.bind(username=username, goal=goal)
    log.info("Recommendations requested")

    # ── Load developer ────────────────────────────────────────────────────
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
                   f"Analyze them first via /analyze/{username}",
        )

    developer_id = str(developer["id"])

    # ── Load skill nodes ──────────────────────────────────────────────────
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

    # ── Get recommendations ───────────────────────────────────────────────
    result = recommender.recommend(gap_vector, top_k=top_k)

    if not result.recommendations:
        raise HTTPException(
            status_code=404,
            detail="No repositories indexed yet. "
                   "Run POST /recommendations/index first.",
        )

    return RecommendationResultOut(
        github_username=username,
        goal_domain=result.goal_domain,
        goal_display_name=result.goal_display_name,
        readiness_score=result.readiness_score,
        recommendations=[
            RepoRecommendationOut(
                full_name=r.full_name,
                description=r.description,
                language=r.language,
                topics=r.topics,
                stars=r.stars,
                newcomer_friendliness=r.newcomer_friendliness,
                relevance_score=r.relevance_score,
                matched_gaps=r.matched_gaps,
                explanation=r.explanation,
            )
            for r in result.recommendations
        ],
        total_found=result.total_found,
        generated_at=datetime.utcnow(),
    )


@router.post("/index", response_model=IndexResultOut)
async def index_repositories(
    background_tasks: BackgroundTasks,
    domains: list[str] | None = None,
):
    """
    Trigger repository indexing in the background.
    This takes 5-15 minutes depending on GitHub rate limits.
    """
    async def run_indexing():
        indexer = RepoIndexer()
        count = await indexer.index_all(domains)
        logger.info("Background indexing complete", count=count)

    background_tasks.add_task(run_indexing)

    return IndexResultOut(
        message="Repository indexing started in background. "
                "This takes 5-15 minutes. "
                "Check logs for progress.",
        status="started",
    )