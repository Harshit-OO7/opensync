"""
API v1 router.
All v1 endpoints are registered here.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import analyze, gap, health

api_router = APIRouter()

api_router.include_router(health.router, prefix="/health", tags=["Health"])
api_router.include_router(analyze.router, prefix="/analyze", tags=["Analyze"])
api_router.include_router(gap.router, prefix="/gap", tags=["Gap Analysis"])

# Phase 3:
# from app.api.v1.endpoints import recommendations
# api_router.include_router(recommendations.router, prefix="/recommendations", tags=["Recommendations"])

# Phase 4:
# from app.api.v1.endpoints import repos
# api_router.include_router(repos.router, prefix="/repos", tags=["Repositories"])