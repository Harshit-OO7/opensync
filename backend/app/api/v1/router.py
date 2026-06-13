"""
API v1 router.
All v1 endpoints are registered here.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import health

api_router = APIRouter()

api_router.include_router(health.router, prefix="/health", tags=["Health"])

# Phase 1 — uncomment as each is implemented:
# from app.api.v1.endpoints import github
# api_router.include_router(github.router, prefix="/github", tags=["GitHub"])

# Phase 2:
# from app.api.v1.endpoints import profiles
# api_router.include_router(profiles.router, prefix="/profiles", tags=["Profiles"])

# Phase 3:
# from app.api.v1.endpoints import recommendations
# api_router.include_router(recommendations.router, prefix="/recommendations", tags=["Recommendations"])

# Phase 4:
# from app.api.v1.endpoints import repos
# api_router.include_router(repos.router, prefix="/repos", tags=["Repositories"])
