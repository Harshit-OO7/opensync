"""
API v1 router.
All v1 endpoints are registered here.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import health, analyze

api_router = APIRouter()

api_router.include_router(health.router, prefix="/health", tags=["Health"])
api_router.include_router(analyze.router, prefix="/analyze", tags=["Analyze"])

# Phase 2:
# from app.api.v1.endpoints import profiles
# api_router.include_router(profiles.router, prefix="/profiles", tags=["Profiles"])

# Phase 3:
# from app.api.v1.endpoints import recommendations
# api_router.include_router(recommendations.router, prefix="/recommendations", tags=["Recommendations"])