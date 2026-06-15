"""
Skill graph builder.

Takes raw skill nodes from the database and builds a structured
confidence-weighted skill graph with trajectory analysis.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone

import structlog

logger = structlog.get_logger()


@dataclass
class SkillNode:
    """A single skill with confidence and trajectory."""
    skill_key: str
    category: str
    confidence: float
    trajectory: str = "unknown"  # growing, stable, declining, unknown
    evidence_count: int = 0
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None


@dataclass
class SkillGraph:
    """
    Complete skill graph for a developer.

    Nodes: individual skills with confidence scores
    Edges: relationships between skills (inferred)
    """
    developer_id: str
    github_username: str
    nodes: dict[str, SkillNode] = field(default_factory=dict)
    global_confidence: float = 0.0
    built_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def get_skill(self, skill_key: str) -> float:
        """Get confidence for a skill, 0.0 if not present."""
        node = self.nodes.get(skill_key)
        return node.confidence if node else 0.0

    def top_skills(self, n: int = 10) -> list[SkillNode]:
        """Return top N skills by confidence."""
        return sorted(
            self.nodes.values(),
            key=lambda x: x.confidence,
            reverse=True,
        )[:n]

    def skills_in_category(self, category: str) -> list[SkillNode]:
        """Return all skills in a given category."""
        return [
            node for node in self.nodes.values()
            if node.category == category
        ]


class SkillGraphBuilder:
    """
    Builds a SkillGraph from raw skill node data.

    Usage:
        builder = SkillGraphBuilder()
        graph = builder.build(developer_id, username, skill_rows)
    """

    def __init__(self):
        self._log = logger.bind(service="skill_graph_builder")

    def build(
        self,
        developer_id: str,
        github_username: str,
        skill_rows: list[dict],
    ) -> SkillGraph:
        """
        Build a skill graph from raw database rows.

        Args:
            developer_id: UUID of the developer
            github_username: GitHub username
            skill_rows: List of dicts with skill_key, category,
                       confidence, evidence_count fields

        Returns:
            SkillGraph with nodes and global confidence
        """
        self._log.info(
            "Building skill graph",
            username=github_username,
            skill_count=len(skill_rows),
        )

        nodes = {}
        for row in skill_rows:
            skill_key = row["skill_key"]
            nodes[skill_key] = SkillNode(
                skill_key=skill_key,
                category=row.get("category", skill_key.split(".")[0]),
                confidence=float(row["confidence"]),
                evidence_count=row.get("evidence_count", 1),
            )

        # Add inferred skills based on relationships
        nodes = self._infer_related_skills(nodes)

        global_confidence = (
            sum(n.confidence for n in nodes.values()) / len(nodes)
            if nodes else 0.0
        )

        graph = SkillGraph(
            developer_id=developer_id,
            github_username=github_username,
            nodes=nodes,
            global_confidence=round(global_confidence, 3),
        )

        self._log.info(
            "Skill graph built",
            username=github_username,
            node_count=len(nodes),
            global_confidence=graph.global_confidence,
        )

        return graph

    def _infer_related_skills(
        self,
        nodes: dict[str, SkillNode],
    ) -> dict[str, SkillNode]:
        """
        Infer additional skills based on known relationships.

        If a developer knows React, they likely know JavaScript.
        If they know Django, they likely know Python.
        """
        inferences = {
            "framework.react": ("language.javascript", 0.7),
            "framework.vue": ("language.javascript", 0.7),
            "framework.django": ("language.python", 0.8),
            "framework.fastapi": ("language.python", 0.8),
            "framework.flask": ("language.python", 0.8),
            "domain.ml": ("language.python", 0.6),
            "tooling.kubernetes": ("tooling.docker", 0.7),
        }

        for source_key, (inferred_key, min_confidence) in inferences.items():
            if source_key in nodes and inferred_key not in nodes:
                source_confidence = nodes[source_key].confidence
                inferred_confidence = min(
                    source_confidence * 0.8, min_confidence
                )
                nodes[inferred_key] = SkillNode(
                    skill_key=inferred_key,
                    category=inferred_key.split(".")[0],
                    confidence=round(inferred_confidence, 3),
                    trajectory="unknown",
                    evidence_count=0,
                )

        return nodes