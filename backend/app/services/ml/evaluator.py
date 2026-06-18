"""
Evaluation framework.

Measures recommendation quality against real contribution outcomes.
Compares our gap-aware system against naive baselines.

Metrics:
- Precision@K: of top K recommendations, how many led to real contributions?
- MRR: Mean Reciprocal Rank — where in the ranking was the first hit?
- Coverage: what % of developers got at least one good recommendation?
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta

import structlog
from github import Github

from app.core.config import settings

logger = structlog.get_logger()


@dataclass
class ContributionOutcome:
    """A real contribution made by a developer."""
    username: str
    repo_full_name: str
    contribution_type: str  # pr_merged, pr_opened, issue_commented
    occurred_at: datetime


@dataclass
class EvaluationResult:
    """Results of evaluating recommendations against real outcomes."""
    username: str
    goal_domain: str
    recommended_repos: list[str]
    actual_contributions: list[str]
    hits: list[str]               # repos in both recommended and contributed
    precision_at_k: float         # hits / k
    reciprocal_rank: float        # 1/rank of first hit, 0 if no hit
    baseline_precision: float     # naive baseline precision
    improvement_over_baseline: float


@dataclass
class EvaluationSummary:
    """Aggregate evaluation across all developers."""
    total_developers: int = 0
    mean_precision_at_5: float = 0.0
    mean_reciprocal_rank: float = 0.0
    coverage: float = 0.0
    baseline_mean_precision: float = 0.0
    mean_improvement: float = 0.0
    results: list[EvaluationResult] = field(default_factory=list)


class Evaluator:
    """
    Evaluates recommendation quality retrospectively.

    For each developer, we:
    1. Look at their GitHub activity BEFORE a cutoff date
    2. Generate recommendations based on that historical profile
    3. Check if they actually contributed to recommended repos AFTER cutoff
    4. Compare against baselines
    """

    def __init__(self):
        self._log = logger.bind(service="evaluator")
        self._github = Github(settings.GITHUB_TOKEN)

    def fetch_recent_contributions(
        self,
        username: str,
        days_back: int = 90,
    ) -> list[ContributionOutcome]:
        """
        Fetch real contributions made by a developer in the last N days.
        Used as ground truth for evaluation.
        """
        outcomes = []
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)

        try:
            user = self._github.get_user(username)

            # Search for merged PRs
            query = f"type:pr author:{username} is:merged is:public"
            results = self._github.search_issues(query)

            for pr in results:
                if pr.created_at < cutoff:
                    continue
                try:
                    outcomes.append(ContributionOutcome(
                        username=username,
                        repo_full_name=pr.repository.full_name,
                        contribution_type="pr_merged",
                        occurred_at=pr.created_at.replace(tzinfo=timezone.utc),
                    ))
                except Exception:
                    continue

        except Exception as e:
            self._log.warning(
                "Failed to fetch contributions",
                username=username,
                error=str(e),
            )

        self._log.info(
            "Contributions fetched",
            username=username,
            count=len(outcomes),
        )
        return outcomes

    def evaluate_single(
        self,
        username: str,
        goal_domain: str,
        recommended_repos: list[str],
        actual_contributions: list[ContributionOutcome],
        baseline_repos: list[str],
        k: int = 5,
    ) -> EvaluationResult:
        """
        Evaluate recommendations for a single developer.

        Args:
            username: GitHub username
            goal_domain: Target goal domain
            recommended_repos: Our system's recommendations (ordered)
            actual_contributions: Real contributions made after analysis
            baseline_repos: Naive baseline recommendations
            k: Number of recommendations to evaluate

        Returns:
            EvaluationResult with precision, MRR, and baseline comparison
        """
        actual_repo_names = {c.repo_full_name for c in actual_contributions}
        top_k = recommended_repos[:k]

        # Find hits
        hits = [r for r in top_k if r in actual_repo_names]

        # Precision@K
        precision = len(hits) / k if k > 0 else 0.0

        # Reciprocal Rank
        rr = 0.0
        for i, repo in enumerate(top_k):
            if repo in actual_repo_names:
                rr = 1.0 / (i + 1)
                break

        # Baseline precision
        baseline_hits = [r for r in baseline_repos[:k] if r in actual_repo_names]
        baseline_precision = len(baseline_hits) / k if k > 0 else 0.0

        improvement = precision - baseline_precision

        result = EvaluationResult(
            username=username,
            goal_domain=goal_domain,
            recommended_repos=top_k,
            actual_contributions=list(actual_repo_names),
            hits=hits,
            precision_at_k=round(precision, 3),
            reciprocal_rank=round(rr, 3),
            baseline_precision=round(baseline_precision, 3),
            improvement_over_baseline=round(improvement, 3),
        )

        self._log.info(
            "Developer evaluated",
            username=username,
            precision=precision,
            mrr=rr,
            hits=len(hits),
        )

        return result

    def summarize(
        self,
        results: list[EvaluationResult],
    ) -> EvaluationSummary:
        """Compute aggregate metrics across all evaluated developers."""
        if not results:
            return EvaluationSummary()

        n = len(results)
        mean_precision = sum(r.precision_at_k for r in results) / n
        mean_rr = sum(r.reciprocal_rank for r in results) / n
        coverage = sum(1 for r in results if r.hits) / n
        baseline_precision = sum(r.baseline_precision for r in results) / n
        mean_improvement = sum(r.improvement_over_baseline for r in results) / n

        summary = EvaluationSummary(
            total_developers=n,
            mean_precision_at_5=round(mean_precision, 3),
            mean_reciprocal_rank=round(mean_rr, 3),
            coverage=round(coverage, 3),
            baseline_mean_precision=round(baseline_precision, 3),
            mean_improvement=round(mean_improvement, 3),
            results=results,
        )

        self._log.info(
            "Evaluation summary",
            developers=n,
            precision=mean_precision,
            mrr=mean_rr,
            coverage=coverage,
            improvement=mean_improvement,
        )

        return summary

    def generate_report(self, summary: EvaluationSummary) -> str:
        """Generate a human-readable evaluation report."""
        lines = [
            "# OpenSync Evaluation Report",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            "## Summary Metrics",
            f"- Developers evaluated: {summary.total_developers}",
            f"- Mean Precision@5: {summary.mean_precision_at_5:.1%}",
            f"- Mean Reciprocal Rank: {summary.mean_reciprocal_rank:.3f}",
            f"- Coverage: {summary.coverage:.1%}",
            "",
            "## vs Baseline",
            f"- Baseline Mean Precision@5: {summary.baseline_mean_precision:.1%}",
            f"- Our Mean Precision@5: {summary.mean_precision_at_5:.1%}",
            f"- Improvement: {summary.mean_improvement:+.1%}",
            "",
            "## Per-Developer Results",
        ]

        for r in summary.results:
            lines.append(f"\n### {r.username} ({r.goal_domain})")
            lines.append(f"- Precision@5: {r.precision_at_k:.1%}")
            lines.append(f"- Reciprocal Rank: {r.reciprocal_rank:.3f}")
            lines.append(f"- Hits: {r.hits or 'none'}")
            lines.append(f"- vs Baseline: {r.improvement_over_baseline:+.1%}")

        return "\n".join(lines)