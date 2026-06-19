"""
Gap-aware repository recommender.

Matches developers to OSS repositories based on their skill gaps,
not their current skills. The objective is trajectory optimization:
find repos that are accessible AND advance the developer toward their goal.
"""

from dataclasses import dataclass, field

import structlog
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, Range, MatchValue
from sentence_transformers import SentenceTransformer

from app.core.config import settings
from app.services.ml.gap_modeler import GapVector

logger = structlog.get_logger()


@dataclass
class RepoRecommendation:
    """A single repository recommendation with explanation."""
    full_name: str
    description: str
    language: str
    topics: list[str]
    stars: int
    newcomer_friendliness: float
    relevance_score: float
    matched_gaps: list[str]
    explanation: str
    domain: str


@dataclass
class RecommendationResult:
    """Complete recommendation result for a developer."""
    github_username: str
    goal_domain: str
    goal_display_name: str
    readiness_score: float
    recommendations: list[RepoRecommendation] = field(default_factory=list)
    total_found: int = 0


class Recommender:
    """
    Gap-aware repository recommender.

    Uses semantic similarity between gap description and repo embeddings
    to find repos that address the developer's specific skill gaps.

    Usage:
        recommender = Recommender()
        result = recommender.recommend(gap_vector, top_k=5)
    """

    COLLECTION_NAME = "repositories"

    def __init__(self):
        self._log = logger.bind(service="recommender")
        self._qdrant = QdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT,
        )
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(settings.EMBEDDING_MODEL)
        except ImportError:
            self._model = None
            self._log.warning("sentence-transformers not available, using fallback")

    def recommend(
        self,
        gap_vector: GapVector,
        top_k: int = 5,
    ) -> RecommendationResult:
        """
        Recommend repositories based on a developer's gap vector.

        Args:
            gap_vector: The computed gap between current skills and goal
            top_k: Number of recommendations to return

        Returns:
            RecommendationResult with ranked repositories
        """
        self._log.info(
            "Generating recommendations",
            username=gap_vector.github_username,
            goal=gap_vector.goal_domain,
            gaps=len(gap_vector.gaps),
        )

        # Build query text from gap vector
        query_text = self._gap_to_query_text(gap_vector)
        self._log.debug("Query text", text=query_text)

        # Embed the query
        if self._model is None:

            return RecommendationResult(
                github_username=gap_vector.github_username,
                goal_domain=gap_vector.goal_domain,
                goal_display_name=gap_vector.goal_display_name,
                readiness_score=gap_vector.readiness_score,
            )
        query_vector = self._model.encode(query_text).tolist()

        # Search Qdrant with domain filter
        try:
            results = self._qdrant.search(
                collection_name=self.COLLECTION_NAME,
                query_vector=query_vector,
                query_filter=Filter(
                    must=[
                        FieldCondition(
                            key="domain",
                            match=MatchValue(value=gap_vector.goal_domain),
                        ),
                        FieldCondition(
                            key="newcomer_friendliness",
                            range=Range(gte=0.1),
                        ),
                    ]
                ),
                limit=top_k * 2,  # fetch more, rerank below
                with_payload=True,
            )
        except Exception as e:
            self._log.error("Qdrant search failed", error=str(e))
            return RecommendationResult(
                github_username=gap_vector.github_username,
                goal_domain=gap_vector.goal_domain,
                goal_display_name=gap_vector.goal_display_name,
                readiness_score=gap_vector.readiness_score,
            )

        if not results:
            self._log.warning(
                "No results from Qdrant",
                goal=gap_vector.goal_domain,
            )
            return RecommendationResult(
                github_username=gap_vector.github_username,
                goal_domain=gap_vector.goal_domain,
                goal_display_name=gap_vector.goal_display_name,
                readiness_score=gap_vector.readiness_score,
            )

        # Rerank and build recommendations
        recommendations = []
        for hit in results:
            payload = hit.payload or {}

            # Compute final score
            semantic_score = hit.score
            friendliness = payload.get("newcomer_friendliness", 0.5)
            final_score = (semantic_score * 0.7) + (friendliness * 0.3)

            # Find which gaps this repo addresses
            matched_gaps = self._find_matched_gaps(
                payload, gap_vector
            )

            # Generate explanation
            explanation = self._generate_explanation(
                payload, gap_vector, matched_gaps
            )

            recommendations.append(RepoRecommendation(
                full_name=payload.get("full_name", ""),
                description=payload.get("description", ""),
                language=payload.get("language", ""),
                topics=payload.get("topics", []),
                stars=payload.get("stars", 0),
                newcomer_friendliness=friendliness,
                relevance_score=round(final_score, 3),
                matched_gaps=matched_gaps,
                explanation=explanation,
                domain=payload.get("domain", ""),
            ))

         # Deduplicate by full_name
            seen = set()
            unique_recommendations = []
            for r in recommendations:
                if r.full_name not in seen:
                    seen.add(r.full_name)
                    unique_recommendations.append(r)
            recommendations = unique_recommendations   

        # Sort by final score and take top_k
        recommendations.sort(key=lambda x: x.relevance_score, reverse=True)
        recommendations = recommendations[:top_k]

        self._log.info(
            "Recommendations generated",
            username=gap_vector.github_username,
            count=len(recommendations),
        )

        return RecommendationResult(
            github_username=gap_vector.github_username,
            goal_domain=gap_vector.goal_domain,
            goal_display_name=gap_vector.goal_display_name,
            readiness_score=gap_vector.readiness_score,
            recommendations=recommendations,
            total_found=len(results),
        )

    def _gap_to_query_text(self, gap_vector: GapVector) -> str:
        """Convert gap vector to natural language query for embedding."""
        goal = gap_vector.goal_display_name
        top_gaps = gap_vector.top_priorities[:3]

        gap_descriptions = []
        for skill_key in top_gaps:
            # Convert skill key to readable text
            readable = skill_key.replace(".", " ").replace("-", " ")
            gap_descriptions.append(f"learning {readable}")

        if gap_descriptions:
            gaps_text = ", ".join(gap_descriptions)
            return (
                f"open source project for {goal}, "
                f"suitable for developer {gaps_text}, "
                f"beginner friendly with good documentation"
            )
        else:
            return f"open source project for {goal}, beginner friendly"

    def _find_matched_gaps(
        self,
        payload: dict,
        gap_vector: GapVector,
    ) -> list[str]:
        """Find which of the developer's gaps this repo addresses."""
        matched = []
        repo_language = (payload.get("language") or "").lower()
        repo_topics = [t.lower() for t in (payload.get("topics") or [])]
        repo_domain = payload.get("domain", "")

        for gap in gap_vector.gaps:
            skill_key = gap.skill_key

            # Language match
            if skill_key.startswith("language."):
                lang = skill_key.replace("language.", "")
                if lang in repo_language or lang in " ".join(repo_topics):
                    matched.append(skill_key)

            # Domain match
            elif skill_key.startswith("domain."):
                domain_part = skill_key.replace("domain.", "")
                if domain_part in repo_domain or any(
                    domain_part in t for t in repo_topics
                ):
                    matched.append(skill_key)

            # Tooling match
            elif skill_key.startswith("tooling."):
                tool = skill_key.replace("tooling.", "")
                if tool in " ".join(repo_topics):
                    matched.append(skill_key)

        # Always add the goal domain as a matched gap
        if not matched:
            matched = [gap_vector.top_priorities[0]] if gap_vector.top_priorities else []

        return matched

    def _generate_explanation(
        self,
        payload: dict,
        gap_vector: GapVector,
        matched_gaps: list[str],
    ) -> str:
        """Generate a human-readable explanation for this recommendation."""
        full_name = payload.get("full_name", "This repo")
        goal = gap_vector.goal_display_name
        friendliness = payload.get("newcomer_friendliness", 0.5)

        if matched_gaps:
            gaps_readable = " and ".join(
                g.replace(".", " ").replace("-", " ")
                for g in matched_gaps[:2]
            )
            explanation = (
                f"{full_name} addresses your gaps in {gaps_readable}. "
            )
        else:
            explanation = f"{full_name} is a strong match for {goal}. "

        if friendliness >= 0.6:
            explanation += "It has excellent newcomer documentation and active maintainers."
        elif friendliness >= 0.4:
            explanation += "It has good contributor resources and a welcoming community."
        else:
            explanation += "It's an active project with opportunities to contribute."

        return explanation