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
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.services.github.client import GitHubClient
from app.services.ml.extractor import FeatureExtractor

logger = structlog.get_logger()
router = APIRouter()

github_client = GitHubClient()
extractor = FeatureExtractor()

# ── Database session ──────────────────────────────────────────────────────────
engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


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
    Results are persisted to the database.
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

    # ── Compute confidence ────────────────────────────────────────────────
    confidence = _compute_confidence(features)

    # ── Persist to database ───────────────────────────────────────────────
    try:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                # Upsert developer record
                await session.execute(
                    text("""
                        INSERT INTO developers (
                            id, github_username, github_id, display_name,
                            avatar_url, profile_confidence, last_analyzed_at,
                            analysis_version, created_at, updated_at
                        ) VALUES (
                            :id, :username, :github_id, :display_name,
                            :avatar_url, :confidence, :analyzed_at,
                            :version, now(), now()
                        )
                        ON CONFLICT (github_username) DO UPDATE SET
                            display_name = EXCLUDED.display_name,
                            avatar_url = EXCLUDED.avatar_url,
                            profile_confidence = EXCLUDED.profile_confidence,
                            last_analyzed_at = EXCLUDED.last_analyzed_at,
                            updated_at = now()
                    """),
                    {
                        "id": developer_id,
                        "username": profile.username,
                        "github_id": profile.github_id,
                        "display_name": profile.display_name,
                        "avatar_url": profile.avatar_url,
                        "confidence": confidence,
                        "analyzed_at": datetime.now(timezone.utc),
                        "version": "v0.1",
                    },
                )

                # Save skill nodes
                for skill_key, confidence_val in _build_skill_nodes(
                    features
                ).items():
                    await session.execute(
                        text("""
                            INSERT INTO skill_nodes (
                                id, developer_id, skill_key, category,
                                confidence, evidence_count,
                                created_at, updated_at
                            ) VALUES (
                                :id, :developer_id, :skill_key, :category,
                                :confidence, :evidence_count, now(), now()
                            )
                            ON CONFLICT (developer_id, skill_key)
                            DO UPDATE SET
                                confidence = EXCLUDED.confidence,
                                evidence_count = EXCLUDED.evidence_count,
                                updated_at = now()
                        """),
                        {
                            "id": str(uuid.uuid4()),
                            "developer_id": developer_id,
                            "skill_key": skill_key,
                            "category": skill_key.split(".")[0],
                            "confidence": confidence_val,
                            "evidence_count": 1,
                        },
                    )

        log.info("Profile saved to database", developer_id=developer_id)

    except Exception as e:
        # Don't fail the request if DB save fails
        log.error("Failed to save to database", error=str(e))

    log.info("Analysis complete", confidence=confidence)

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


def _build_skill_nodes(features) -> dict[str, float]:
    """Build skill key → confidence mapping from feature vector."""
    skills = {}

    # Language skills
    for lang, ratio in features.language_signals.language_distribution.items():
        if ratio > 0.05:
            skill_key = f"language.{lang.lower()}"
            skills[skill_key] = min(ratio * 1.5, 1.0)

    # Framework and domain signals
    for framework in features.language_signals.detected_frameworks:
        skills[framework] = 0.6

    for domain in features.language_signals.detected_domains:
        skills[domain] = 0.5

    for tooling in features.language_signals.detected_tooling:
        skills[tooling] = 0.5

    # Practice signals from commit quality
    if features.commit_quality.quality_score > 0.5:
        skills["practice.clean-commits"] = features.commit_quality.quality_score

    if features.repo_quality.has_tests_ratio > 0.3:
        skills["practice.testing"] = features.repo_quality.has_tests_ratio

    if features.repo_quality.has_ci_ratio > 0.2:
        skills["practice.ci-cd"] = features.repo_quality.has_ci_ratio

    # Collaboration signal
    if features.collaboration.contributes_to_others:
        skills["practice.open-source-contribution"] = (
            features.collaboration.merged_pr_ratio or 0.3
        )

    return skills


def _compute_confidence(features) -> float:
    """Compute overall profile confidence score (0-1)."""
    score = 0.0

    if features.commit_quality.total_commits > 0:
        commit_score = min(features.commit_quality.total_commits / 100, 1.0)
        score += commit_score * 0.4

    if features.repo_quality.total_repos > 0:
        repo_score = min(features.repo_quality.total_repos / 20, 1.0)
        score += repo_score * 0.35

    if features.language_signals.primary_language:
        score += 0.15

    if features.collaboration.total_prs > 0:
        score += 0.10

    return round(score, 3)