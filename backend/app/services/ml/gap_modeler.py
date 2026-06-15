"""
Gap modeler.

Computes the vector representing what a developer needs to learn
to reach their stated goal domain.

gap = target_profile - current_skill_graph
Positive values = skills to learn
Negative values = skills that exceed requirements
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone

import structlog

from app.services.ml.skill_graph import SkillGraph
from app.services.ml.target_profiles import TargetProfile, get_profile

logger = structlog.get_logger()


@dataclass
class SkillGap:
    """A single skill gap."""
    skill_key: str
    category: str
    required_confidence: float
    current_confidence: float
    gap_size: float          # positive = need to learn, negative = exceeds
    priority: str            # high, medium, low


@dataclass
class GapVector:
    """
    Complete gap analysis between current skills and target goal.
    """
    developer_id: str
    github_username: str
    goal_domain: str
    goal_display_name: str

    # Skills that need work (gap_size > 0)
    gaps: list[SkillGap] = field(default_factory=list)

    # Skills already meeting requirements
    satisfied: list[SkillGap] = field(default_factory=list)

    # Overall readiness score (0-1)
    # 1.0 = fully ready, 0.0 = not ready at all
    readiness_score: float = 0.0

    # Top 3 skills to focus on
    top_priorities: list[str] = field(default_factory=list)

    computed_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class GapModeler:
    """
    Computes gap vectors between skill graphs and target profiles.

    Usage:
        modeler = GapModeler()
        gap = modeler.compute(skill_graph, "ai-ml-tooling")
    """

    # Minimum gap size to include in results
    GAP_THRESHOLD = 0.10

    def __init__(self):
        self._log = logger.bind(service="gap_modeler")

    def compute(
        self,
        skill_graph: SkillGraph,
        goal_domain: str,
    ) -> GapVector:
        """
        Compute the gap between a developer's skills and a goal domain.

        Args:
            skill_graph: Developer's current skill graph
            goal_domain: Target domain key (e.g. 'ai-ml-tooling')

        Returns:
            GapVector with gaps, satisfied skills, and readiness score
        """
        target = get_profile(goal_domain)
        if not target:
            raise ValueError(f"Unknown goal domain: '{goal_domain}'")

        self._log.info(
            "Computing gap",
            username=skill_graph.github_username,
            goal=goal_domain,
        )

        gaps = []
        satisfied = []

        # Check all required skills
        for skill_key, required_conf in target.required.items():
            current_conf = skill_graph.get_skill(skill_key)
            gap_size = required_conf - current_conf

            skill_gap = SkillGap(
                skill_key=skill_key,
                category=skill_key.split(".")[0],
                required_confidence=required_conf,
                current_confidence=round(current_conf, 3),
                gap_size=round(gap_size, 3),
                priority=self._compute_priority(gap_size, "required"),
            )

            if gap_size > self.GAP_THRESHOLD:
                gaps.append(skill_gap)
            else:
                satisfied.append(skill_gap)

        # Check helpful skills
        for skill_key, required_conf in target.helpful.items():
            current_conf = skill_graph.get_skill(skill_key)
            gap_size = required_conf - current_conf

            if gap_size > self.GAP_THRESHOLD:
                skill_gap = SkillGap(
                    skill_key=skill_key,
                    category=skill_key.split(".")[0],
                    required_confidence=required_conf,
                    current_confidence=round(current_conf, 3),
                    gap_size=round(gap_size, 3),
                    priority=self._compute_priority(gap_size, "helpful"),
                )
                gaps.append(skill_gap)

        # Sort gaps by priority then gap size
        priority_order = {"high": 0, "medium": 1, "low": 2}
        gaps.sort(key=lambda x: (priority_order[x.priority], -x.gap_size))

        # Compute readiness score
        readiness_score = self._compute_readiness(
            skill_graph, target, satisfied, gaps
        )

        # Top 3 priorities
        top_priorities = [g.skill_key for g in gaps[:3]]

        gap_vector = GapVector(
            developer_id=skill_graph.developer_id,
            github_username=skill_graph.github_username,
            goal_domain=goal_domain,
            goal_display_name=target.display_name,
            gaps=gaps,
            satisfied=satisfied,
            readiness_score=readiness_score,
            top_priorities=top_priorities,
        )

        self._log.info(
            "Gap computed",
            username=skill_graph.github_username,
            goal=goal_domain,
            readiness=readiness_score,
            gap_count=len(gaps),
            satisfied_count=len(satisfied),
        )

        return gap_vector

    def _compute_priority(
        self,
        gap_size: float,
        skill_type: str,
    ) -> str:
        """Assign priority based on gap size and skill type."""
        if skill_type == "required":
            if gap_size > 0.5:
                return "high"
            elif gap_size > 0.25:
                return "medium"
            else:
                return "low"
        else:  # helpful
            if gap_size > 0.4:
                return "medium"
            else:
                return "low"

    def _compute_readiness(
        self,
        skill_graph: SkillGraph,
        target: TargetProfile,
        satisfied: list[SkillGap],
        gaps: list[SkillGap],
    ) -> float:
        """
        Compute overall readiness score (0-1).

        Based on how many required skills are satisfied
        and how close the developer is on unsatisfied ones.
        """
        if not target.required:
            return 0.5

        total_required = len(target.required)
        satisfied_required = sum(
            1 for s in satisfied
            if s.skill_key in target.required
        )

        # Base score from satisfied requirements
        base_score = satisfied_required / total_required

        # Partial credit for skills that are close
        partial_credit = 0.0
        for gap in gaps:
            if gap.skill_key in target.required:
                # If you have 50% of what's needed, get 50% partial credit
                ratio = gap.current_confidence / gap.required_confidence
                partial_credit += ratio / total_required

        readiness = (base_score + partial_credit) / 2
        return round(min(readiness, 1.0), 3)