"""
API v1 router.
All v1 endpoints are registered here.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import analyze, evaluation, gap, guide, health, recommendations

api_router = APIRouter()

api_router.include_router(health.router, prefix="/health", tags=["Health"])
api_router.include_router(analyze.router, prefix="/analyze", tags=["Analyze"])
api_router.include_router(gap.router, prefix="/gap", tags=["Gap Analysis"])
api_router.include_router(
    recommendations.router,
    prefix="/recommendations",
    tags=["Recommendations"],
)
api_router.include_router(guide.router, prefix="/guide", tags=["Repo Guide"])
api_router.include_router(
    evaluation.router,
    prefix="/evaluation",
    tags=["Evaluation"],
)