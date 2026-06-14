"""
Behavioral feature extractor.

Takes a RawGitHubProfile and extracts structured behavioral signals.
These signals form the basis of the skill graph.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

import structlog

from app.services.github.client import RawCommit, RawGitHubProfile, RawRepo

logger = structlog.get_logger()

# ── Constants ─────────────────────────────────────────────────────────────────

# Generic commit messages that provide no signal
GENERIC_MESSAGES = {
    "initial commit", "init", "update", "fix", "wip",
    "minor changes", "minor fix", "cleanup", "refactor",
    "test", "testing", "temp", "tmp", "done", "working",
    "changes", "update readme", "add files", "first commit",
}

# Files that indicate testing knowledge
TEST_FILE_PATTERNS = [
    r"test_.*\.py$", r".*_test\.py$", r".*\.test\.[jt]sx?$",
    r".*\.spec\.[jt]sx?$", r"__tests__/", r"tests?/",
]

# CI configuration files
CI_FILE_PATTERNS = [
    ".github/workflows/", ".circleci/", "Jenkinsfile",
    ".travis.yml", "azure-pipelines.yml", ".gitlab-ci.yml",
    "bitbucket-pipelines.yml",
]

# Framework detection patterns in repo names/descriptions/topics
FRAMEWORK_SIGNALS = {
    "language.python": ["python", "django", "flask", "fastapi", "pytest"],
    "language.javascript": ["javascript", "nodejs", "node", "npm", "webpack"],
    "language.typescript": ["typescript", "ts", "angular", "nestjs"],
    "language.go": ["golang", "go"],
    "language.rust": ["rust", "cargo"],
    "language.java": ["java", "spring", "maven", "gradle"],
    "language.cpp": ["cpp", "c++", "cmake"],
    "language.ruby": ["ruby", "rails", "gem"],
    "framework.react": ["react", "nextjs", "next.js", "gatsby"],
    "framework.vue": ["vue", "nuxt"],
    "framework.django": ["django"],
    "framework.fastapi": ["fastapi"],
    "framework.flask": ["flask"],
    "domain.ml": ["machine-learning", "ml", "deep-learning", "pytorch",
                  "tensorflow", "keras", "sklearn", "huggingface"],
    "domain.web-backend": ["api", "backend", "rest", "graphql", "microservice"],
    "domain.web-frontend": ["frontend", "ui", "css", "html", "web"],
    "domain.infrastructure": ["docker", "kubernetes", "k8s", "terraform",
                               "ansible", "devops", "infrastructure"],
    "domain.data": ["data", "etl", "pipeline", "spark", "kafka", "airflow"],
    "tooling.docker": ["docker", "dockerfile", "container"],
    "tooling.kubernetes": ["kubernetes", "k8s", "helm"],
}


@dataclass
class CommitQualitySignals:
    """Quality signals extracted from commit messages."""
    total_commits: int = 0
    generic_ratio: float = 0.0          # ratio of generic messages
    avg_message_length: float = 0.0
    imperative_mood_ratio: float = 0.0  # starts with verb
    multi_line_ratio: float = 0.0       # has body/description
    atomic_ratio: float = 0.0           # single-purpose commits
    quality_score: float = 0.0          # overall 0-1 score


@dataclass
class RepoQualitySignals:
    """Quality signals extracted from repository structure."""
    total_repos: int = 0
    has_tests_ratio: float = 0.0        # repos with test files
    has_ci_ratio: float = 0.0           # repos with CI config
    has_readme_ratio: float = 0.0       # repos with README
    has_description_ratio: float = 0.0  # repos with description
    avg_stars: float = 0.0
    quality_score: float = 0.0


@dataclass
class LanguageSignals:
    """Language and framework signals."""
    primary_language: str | None = None
    language_distribution: dict[str, float] = field(default_factory=dict)
    detected_frameworks: list[str] = field(default_factory=list)
    detected_domains: list[str] = field(default_factory=list)
    detected_tooling: list[str] = field(default_factory=list)


@dataclass
class CollaborationSignals:
    """Collaboration and community signals."""
    total_prs: int = 0
    merged_pr_ratio: float = 0.0
    avg_pr_comments: float = 0.0
    contributes_to_others: bool = False  # PRs to repos they don't own


@dataclass
class FeatureVector:
    """
    Complete set of behavioral features extracted from a GitHub profile.
    This is the input to the skill graph builder.
    """
    developer_id: str
    github_username: str
    extracted_at: datetime

    commit_quality: CommitQualitySignals = field(
        default_factory=CommitQualitySignals
    )
    repo_quality: RepoQualitySignals = field(
        default_factory=RepoQualitySignals
    )
    language_signals: LanguageSignals = field(
        default_factory=LanguageSignals
    )
    collaboration: CollaborationSignals = field(
        default_factory=CollaborationSignals
    )

    # Raw counts for reference
    total_public_repos: int = 0
    account_age_days: int = 0


class FeatureExtractor:
    """
    Extracts behavioral features from a raw GitHub profile.

    Usage:
        extractor = FeatureExtractor()
        features = extractor.extract("user-uuid", profile)
    """

    def __init__(self):
        self._log = logger.bind(service="feature_extractor")

    def extract(
        self,
        developer_id: str,
        profile: RawGitHubProfile,
    ) -> FeatureVector:
        """
        Extract all behavioral features from a raw GitHub profile.

        Args:
            developer_id: UUID of the developer record in DB
            profile: Raw GitHub profile data

        Returns:
            FeatureVector with all extracted signals
        """
        self._log.info(
            "Extracting features",
            username=profile.username,
            repos=len(profile.repos),
            commits=len(profile.commits),
        )

        now = datetime.now(timezone.utc)
        account_age = (now - profile.created_at.replace(
            tzinfo=timezone.utc
        )).days

        features = FeatureVector(
            developer_id=developer_id,
            github_username=profile.username,
            extracted_at=now,
            total_public_repos=profile.public_repos,
            account_age_days=account_age,
            commit_quality=self._extract_commit_quality(profile.commits),
            repo_quality=self._extract_repo_quality(profile.repos),
            language_signals=self._extract_language_signals(profile.repos),
            collaboration=self._extract_collaboration(
                profile.username, profile.pull_requests
            ),
        )

        self._log.info(
            "Features extracted",
            username=profile.username,
            commit_quality=features.commit_quality.quality_score,
            repo_quality=features.repo_quality.quality_score,
            primary_language=features.language_signals.primary_language,
        )

        return features

    # ── Private extraction methods ────────────────────────────────────────────

    def _extract_commit_quality(
        self,
        commits: list[RawCommit],
    ) -> CommitQualitySignals:
        """Score commit message quality as behavioral signal."""
        if not commits:
            return CommitQualitySignals()

        total = len(commits)
        generic_count = 0
        imperative_count = 0
        multi_line_count = 0
        atomic_count = 0
        lengths = []

        # Common imperative verbs that start good commit messages
        imperative_verbs = {
            "add", "fix", "update", "remove", "refactor", "implement",
            "create", "delete", "rename", "move", "improve", "clean",
            "bump", "change", "extract", "merge", "revert", "support",
            "allow", "prevent", "handle", "use", "make", "enable",
        }

        for commit in commits:
            msg = commit.message.strip()
            first_line = msg.split("\n")[0].strip().lower()

            # Generic check
            if first_line in GENERIC_MESSAGES or len(first_line) < 10:
                generic_count += 1

            # Imperative mood check
            first_word = first_line.split()[0] if first_line.split() else ""
            if first_word in imperative_verbs:
                imperative_count += 1

            # Multi-line check (has body)
            if "\n" in msg and len(msg.split("\n")) > 2:
                multi_line_count += 1

            # Atomic check (reasonable file count)
            if 0 < commit.files_changed <= 5:
                atomic_count += 1

            lengths.append(len(first_line))

        generic_ratio = generic_count / total
        imperative_ratio = imperative_count / total
        multi_line_ratio = multi_line_count / total
        atomic_ratio = atomic_count / total
        avg_length = sum(lengths) / len(lengths)

        # Quality score: weighted combination
        quality_score = (
            (1 - generic_ratio) * 0.3
            + imperative_ratio * 0.25
            + multi_line_ratio * 0.2
            + atomic_ratio * 0.25
        )

        return CommitQualitySignals(
            total_commits=total,
            generic_ratio=round(generic_ratio, 3),
            avg_message_length=round(avg_length, 1),
            imperative_mood_ratio=round(imperative_ratio, 3),
            multi_line_ratio=round(multi_line_ratio, 3),
            atomic_ratio=round(atomic_ratio, 3),
            quality_score=round(quality_score, 3),
        )

    def _extract_repo_quality(
        self,
        repos: list[RawRepo],
    ) -> RepoQualitySignals:
        """Score repository structure quality."""
        if not repos:
            return RepoQualitySignals()

        total = len(repos)
        has_description = sum(
            1 for r in repos if r.description and len(r.description) > 10
        )

        # We infer test/CI presence from topics and language
        # Full file tree analysis comes in Phase 2
        has_tests = sum(
            1 for r in repos
            if any(t in (r.topics or []) for t in ["testing", "tests", "pytest"])
            or (r.language and r.language.lower() in ["python", "javascript",
                                                        "typescript"])
        )
        has_ci = sum(
            1 for r in repos
            if any(t in (r.topics or []) for t in
                   ["ci", "github-actions", "travis-ci"])
        )

        avg_stars = sum(r.stars for r in repos) / total

        quality_score = (
            (has_description / total) * 0.3
            + (has_tests / total) * 0.4
            + (has_ci / total) * 0.3
        )

        return RepoQualitySignals(
            total_repos=total,
            has_tests_ratio=round(has_tests / total, 3),
            has_ci_ratio=round(has_ci / total, 3),
            has_readme_ratio=round(has_description / total, 3),
            has_description_ratio=round(has_description / total, 3),
            avg_stars=round(avg_stars, 1),
            quality_score=round(quality_score, 3),
        )

    def _extract_language_signals(
        self,
        repos: list[RawRepo],
    ) -> LanguageSignals:
        """Extract language and framework signals from repos."""
        if not repos:
            return LanguageSignals()

        # Aggregate language bytes across all repos
        lang_bytes: dict[str, int] = {}
        for repo in repos:
            for lang, bytes_count in repo.languages.items():
                lang_bytes[lang] = lang_bytes.get(lang, 0) + bytes_count

        # Normalize to percentages
        total_bytes = sum(lang_bytes.values()) or 1
        lang_distribution = {
            lang: round(count / total_bytes, 3)
            for lang, count in sorted(
                lang_bytes.items(), key=lambda x: -x[1]
            )
        }

        primary_language = (
            max(lang_bytes, key=lang_bytes.get) if lang_bytes else None
        )

        # Detect frameworks/domains from topics and descriptions
        all_text = " ".join([
            " ".join(r.topics or [])
            + " " + (r.description or "")
            + " " + (r.name or "")
            for r in repos
        ]).lower()

        detected_frameworks = []
        detected_domains = []
        detected_tooling = []

        for signal_key, keywords in FRAMEWORK_SIGNALS.items():
            if any(kw in all_text for kw in keywords):
                if signal_key.startswith("framework."):
                    detected_frameworks.append(signal_key)
                elif signal_key.startswith("domain."):
                    detected_domains.append(signal_key)
                elif signal_key.startswith("tooling."):
                    detected_tooling.append(signal_key)

        # Also add language signals from the distribution
        for lang in list(lang_distribution.keys())[:5]:
            lang_key = f"language.{lang.lower()}"
            if lang_distribution[lang] > 0.05:  # >5% of code
                if lang_key not in detected_frameworks:
                    detected_frameworks.append(lang_key)

        return LanguageSignals(
            primary_language=primary_language,
            language_distribution=lang_distribution,
            detected_frameworks=detected_frameworks,
            detected_domains=detected_domains,
            detected_tooling=detected_tooling,
        )

    def _extract_collaboration(
        self,
        username: str,
        pull_requests,
    ) -> CollaborationSignals:
        """Extract collaboration signals from pull request history."""
        if not pull_requests:
            return CollaborationSignals()

        total = len(pull_requests)
        merged = sum(1 for pr in pull_requests if pr.merged_at is not None)
        avg_comments = (
            sum(pr.comments for pr in pull_requests) / total
            if total > 0 else 0
        )

        # Check if they contribute to repos they don't own
        contributes_to_others = any(
            not pr.repo_full_name.startswith(f"{username}/")
            for pr in pull_requests
        )

        return CollaborationSignals(
            total_prs=total,
            merged_pr_ratio=round(merged / total, 3) if total > 0 else 0.0,
            avg_pr_comments=round(avg_comments, 1),
            contributes_to_others=contributes_to_others,
        )