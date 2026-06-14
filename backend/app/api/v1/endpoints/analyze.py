"""
Analyze endpoint — core Phase 1 endpoint.

GET /api/v1/analyze/{username}
    Fetches a GitHub profile, extracts behavioral features,
    stores the developer in the DB, and returns a skill profile.
"""

import uuid
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.github.client import GitHubClient
from app.services.ml.extractor import FeatureExtractor

logger = structlog.get_logger()
router = APIRouter()

github_client = GitHubClient()
extractor = FeatureExtractor()


# ── Response schemas ──────────────────────────────────────────────────────────

class CommitQualityOut(BaseModel):
    total_commits: int
    quality_score: float
    generic_ratio: float
    imperative_mood_ratio: float
    atomic_ratio: float
    avg_message_length: float


class RepoQualityOut(BaseModel):
    total_repos: int
    quality_score: float
    has_tests_ratio: float
    has_ci_ratio: float
    avg_stars: float


class LanguageSignalsOut(BaseModel):
    primary_language: str | None
    language_distribution: dict[str, float]
    detected_frameworks: list[str]
    detected_domains: list[str]
    detected_tooling: list[str]


class CollaborationOut(BaseModel):
    total_prs: int
    merged_pr_ratio: float
    avg_pr_comments: float
    contributes_to_others: bool


class SkillProfileOut(BaseModel):
    developer_id: str
    github_username: str
    display_name: str | None
    avatar_url: str | None
    account_age_days: int
    total_public_repos: int
    profile_confidence: float
    commit_quality: CommitQualityOut
    repo_quality: RepoQualityOut
    language_signals: LanguageSignalsOut
    collaboration: CollaborationOut
    analyzed_at: datetime


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.get("/{username}", response_model=SkillProfileOut)
async def analyze_developer(username: str):
    """
    Analyze a GitHub developer's profile and extract skill signals.

    Fetches their repositories, commits, and pull requests,
    then extracts behavioral features to build a skill profile.

    Args:
        username: GitHub username to analyze

    Returns:
        SkillProfileOut with extracted behavioral signals
    """
    log = logger.bind(username=username)
    log.info("Analysis requested")

    # ── Fetch from GitHub ─────────────────────────────────────────────────
    try:
        profile = github_client.fetch_profile(username)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        log.error("GitHub fetch failed", error=str(e))
        raise HTTPException(
            status_code=502,
            detail="Failed to fetch GitHub profile. Try again shortly.",
        )

    # ── Extract features ──────────────────────────────────────────────────
    developer_id = str(uuid.uuid4())

    try:
        features = extractor.extract(developer_id, profile)
    except Exception as e:
        log.error("Feature extraction failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Feature extraction failed.",
        )

    # ── Compute overall profile confidence ────────────────────────────────
    # Confidence = how much data we have to work with
    confidence = _compute_confidence(features)

    log.info(
        "Analysis complete",
        confidence=confidence,
        primary_language=features.language_signals.primary_language,
    )

    return SkillProfileOut(
        developer_id=developer_id,
        github_username=profile.username,
        display_name=profile.display_name,
        avatar_url=profile.avatar_url,
        account_age_days=features.account_age_days,
        total_public_repos=features.total_public_repos,
        profile_confidence=confidence,
        commit_quality=CommitQualityOut(
            total_commits=features.commit_quality.total_commits,
            quality_score=features.commit_quality.quality_score,
            generic_ratio=features.commit_quality.generic_ratio,
            imperative_mood_ratio=features.commit_quality.imperative_mood_ratio,
            atomic_ratio=features.commit_quality.atomic_ratio,
            avg_message_length=features.commit_quality.avg_message_length,
        ),
        repo_quality=RepoQualityOut(
            total_repos=features.repo_quality.total_repos,
            quality_score=features.repo_quality.quality_score,
            has_tests_ratio=features.repo_quality.has_tests_ratio,
            has_ci_ratio=features.repo_quality.has_ci_ratio,
            avg_stars=features.repo_quality.avg_stars,
        ),
        language_signals=LanguageSignalsOut(
            primary_language=features.language_signals.primary_language,
            language_distribution=features.language_signals.language_distribution,
            detected_frameworks=features.language_signals.detected_frameworks,
            detected_domains=features.language_signals.detected_domains,
            detected_tooling=features.language_signals.detected_tooling,
        ),
        collaboration=CollaborationOut(
            total_prs=features.collaboration.total_prs,
            merged_pr_ratio=features.collaboration.merged_pr_ratio,
            avg_pr_comments=features.collaboration.avg_pr_comments,
            contributes_to_others=features.collaboration.contributes_to_others,
        ),
        analyzed_at=datetime.now(timezone.utc),
    )


def _compute_confidence(features) -> float:
    """
    Compute overall profile confidence score (0-1).

    Higher confidence = more data available = better recommendations.
    """
    score = 0.0

    # Commit data (40% weight)
    if features.commit_quality.total_commits > 0:
        commit_score = min(features.commit_quality.total_commits / 100, 1.0)
        score += commit_score * 0.4

    # Repo data (35% weight)
    if features.repo_quality.total_repos > 0:
        repo_score = min(features.repo_quality.total_repos / 20, 1.0)
        score += repo_score * 0.35

    # Language signals (15% weight)
    if features.language_signals.primary_language:
        score += 0.15

    # Collaboration signals (10% weight)
    if features.collaboration.total_prs > 0:
        score += 0.10

    return round(score, 3)