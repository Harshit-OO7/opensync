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
    """

    COLLECTION_NAME = "repositories"

    def __init__(self):
        self._log = logger.bind(service="recommender")

        # Connect to Qdrant
        if settings.QDRANT_API_KEY:
            self._qdrant = QdrantClient(
                url=f"https://{settings.QDRANT_HOST}",
                api_key=settings.QDRANT_API_KEY,
            )
        else:
            self._qdrant = QdrantClient(
                host=settings.QDRANT_HOST,
                port=settings.QDRANT_PORT,
            )

        # Try to load embedding model
        self._model = None
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(settings.EMBEDDING_MODEL)
            self._log.info("Embedding model loaded")
        except Exception:
            self._log.warning("sentence-transformers not available, using fallback")

    def recommend(
        self,
        gap_vector: GapVector,
        top_k: int = 5,
    ) -> RecommendationResult:
        """
        Recommend repositories based on a developer's gap vector.
        """
        self._log.info(
            "Generating recommendations",
            username=gap_vector.github_username,
            goal=gap_vector.goal_domain,
            gaps=len(gap_vector.gaps),
        )

        try:
            if self._model is not None:
                # Use semantic search with embeddings
                query_text = self._gap_to_query_text(gap_vector)
                query_vector = self._model.encode(query_text).tolist()

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
                    limit=top_k * 2,
                    with_payload=True,
                )
                self._log.info("Semantic search results", count=len(results))

            else:
                # Fallback: scroll all and filter by domain in Python
                self._log.info("Using scroll fallback", goal=gap_vector.goal_domain)

                all_points, _ = self._qdrant.scroll(
                    collection_name=self.COLLECTION_NAME,
                    limit=100,
                    with_payload=True,
                    with_vectors=False,
                )

                self._log.info("Total points in Qdrant", count=len(all_points))

                filtered = [
                    p for p in all_points
                    if p.payload is not None
                    and p.payload.get("domain") == gap_vector.goal_domain
                ]

                self._log.info(
                    "Filtered by domain",
                    domain=gap_vector.goal_domain,
                    count=len(filtered),
                )

                class FakeHit:
                    def __init__(self, point):
                        self.score = point.payload.get("newcomer_friendliness", 0.5)
                        self.payload = point.payload

                results = [FakeHit(p) for p in filtered]

        except Exception as e:
            self._log.error("Qdrant search failed", error=str(e))
            return RecommendationResult(
                github_username=gap_vector.github_username,
                goal_domain=gap_vector.goal_domain,
                goal_display_name=gap_vector.goal_display_name,
                readiness_score=gap_vector.readiness_score,
            )

        if not results:
            self._log.warning("No results found", goal=gap_vector.goal_domain)
            return RecommendationResult(
                github_username=gap_vector.github_username,
                goal_domain=gap_vector.goal_domain,
                goal_display_name=gap_vector.goal_display_name,
                readiness_score=gap_vector.readiness_score,
            )

        # Build recommendations
        recommendations = []
        seen = set()

        for hit in results:
            payload = hit.payload or {}
            full_name = payload.get("full_name", "")

            if full_name in seen or not full_name:
                continue
            seen.add(full_name)

            semantic_score = hit.score
            friendliness = payload.get("newcomer_friendliness", 0.5)
            final_score = (semantic_score * 0.7) + (friendliness * 0.3)

            matched_gaps = self._find_matched_gaps(payload, gap_vector)
            explanation = self._generate_explanation(payload, gap_vector, matched_gaps)

            recommendations.append(RepoRecommendation(
                full_name=full_name,
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
            readable = skill_key.replace(".", " ").replace("-", " ")
            gap_descriptions.append(f"learning {readable}")

        if gap_descriptions:
            gaps_text = ", ".join(gap_descriptions)
            return (
                f"open source project for {goal}, "
                f"suitable for developer {gaps_text}, "
                f"beginner friendly with good documentation"
            )
        return f"open source project for {goal}, beginner friendly"

    def _find_matched_gaps(self, payload: dict, gap_vector: GapVector) -> list[str]:
        """Find which of the developer's gaps this repo addresses."""
        matched = []
        repo_language = (payload.get("language") or "").lower()
        repo_topics = [t.lower() for t in (payload.get("topics") or [])]
        repo_domain = payload.get("domain", "")

        for gap in gap_vector.gaps:
            skill_key = gap.skill_key

            if skill_key.startswith("language."):
                lang = skill_key.replace("language.", "")
                if lang in repo_language or lang in " ".join(repo_topics):
                    matched.append(skill_key)

            elif skill_key.startswith("domain."):
                domain_part = skill_key.replace("domain.", "")
                if domain_part in repo_domain or any(
                    domain_part in t for t in repo_topics
                ):
                    matched.append(skill_key)

            elif skill_key.startswith("tooling."):
                tool = skill_key.replace("tooling.", "")
                if tool in " ".join(repo_topics):
                    matched.append(skill_key)

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
            explanation = f"{full_name} addresses your gaps in {gaps_readable}. "
        else:
            explanation = f"{full_name} is a strong match for {goal}. "

        if friendliness >= 0.6:
            explanation += "It has excellent newcomer documentation and active maintainers."
        elif friendliness >= 0.4:
            explanation += "It has good contributor resources and a welcoming community."
        else:
            explanation += "It's an active project with opportunities to contribute."

        return explanation