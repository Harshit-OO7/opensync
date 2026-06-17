"""
RAG-powered repository guide.

Fetches repo README/docs, chunks them, and generates
a personalized explanation based on the developer's
skill profile and gap vector.
"""

import structlog
from github import Github
from groq import Groq

from app.core.config import settings
from app.services.ml.gap_modeler import GapVector

logger = structlog.get_logger()


class RepoGuide:
    """
    Generates personalized repo explanations using RAG.

    Usage:
        guide = RepoGuide()
        explanation = guide.explain(repo_name, gap_vector)
    """

    def __init__(self):
        self._log = logger.bind(service="repo_guide")
        self._github = Github(settings.GITHUB_TOKEN)
        self._groq = Groq(api_key=settings.GROQ_API_KEY)

    def explain(
        self,
        repo_full_name: str,
        gap_vector: GapVector,
        max_readme_chars: int = 3000,
    ) -> dict:
        """
        Generate a personalized explanation of a repository.

        Args:
            repo_full_name: e.g. 'huggingface/datasets'
            gap_vector: Developer's gap vector with skills and goals
            max_readme_chars: Max README chars to include in context

        Returns:
            dict with explanation, entry_points, and suggested_issues
        """
        self._log.info(
            "Generating repo guide",
            repo=repo_full_name,
            username=gap_vector.github_username,
        )

        # ── Fetch repo context ────────────────────────────────────────────
        readme_text = self._fetch_readme(repo_full_name, max_readme_chars)
        repo_info = self._fetch_repo_info(repo_full_name)

        # ── Build personalized prompt ─────────────────────────────────────
        prompt = self._build_prompt(
            repo_full_name, readme_text, repo_info, gap_vector
        )

        # ── Generate explanation ──────────────────────────────────────────
        try:
            response = self._groq.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a senior open source contributor helping "
                            "a developer understand a repository and find their "
                            "first contribution. Be specific, practical, and "
                            "encouraging. Format your response as JSON."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=1000,
            )

            raw = response.choices[0].message.content
            result = self._parse_response(raw)

        except Exception as e:
            self._log.error("LLM call failed", error=str(e))
            result = self._fallback_explanation(repo_full_name, gap_vector)

        self._log.info("Repo guide generated", repo=repo_full_name)
        return result

    def _fetch_readme(self, repo_full_name: str, max_chars: int) -> str:
        """Fetch and truncate repo README."""
        try:
            repo = self._github.get_repo(repo_full_name)
            readme = repo.get_readme()
            content = readme.decoded_content.decode("utf-8", errors="ignore")
            return content[:max_chars]
        except Exception as e:
            self._log.warning("README fetch failed", repo=repo_full_name, error=str(e))
            return "README not available."

    def _fetch_repo_info(self, repo_full_name: str) -> dict:
        """Fetch basic repo metadata."""
        try:
            repo = self._github.get_repo(repo_full_name)
            topics = repo.get_topics()
            return {
                "description": repo.description or "",
                "language": repo.language or "",
                "stars": repo.stargazers_count,
                "topics": topics,
                "open_issues": repo.open_issues_count,
                "has_contributing": False,
            }
        except Exception:
            return {}

    def _build_prompt(
        self,
        repo_full_name: str,
        readme: str,
        repo_info: dict,
        gap_vector: GapVector,
    ) -> str:
        """Build a personalized prompt for the LLM."""
        # Developer context
        username = gap_vector.github_username
        goal = gap_vector.goal_display_name
        top_gaps = gap_vector.top_priorities[:3]
        satisfied = [s.skill_key for s in gap_vector.satisfied[:3]]

        gaps_text = ", ".join(top_gaps) if top_gaps else "general skills"
        satisfied_text = ", ".join(satisfied) if satisfied else "basic programming"

        return f"""
A developer named {username} wants to contribute to {repo_full_name}.

DEVELOPER PROFILE:
- Goal: Contribute to {goal} projects
- Skills they already have: {satisfied_text}
- Skills they need to develop: {gaps_text}
- Readiness score: {gap_vector.readiness_score}/1.0

REPOSITORY INFO:
- Description: {repo_info.get('description', '')}
- Primary language: {repo_info.get('language', '')}
- Topics: {', '.join(repo_info.get('topics', []))}
- Open issues: {repo_info.get('open_issues', 0)}
- Stars: {repo_info.get('stars', 0)}

README (truncated):
{readme[:2000]}

Please respond with a JSON object containing exactly these fields:
{{
    "summary": "2-3 sentence explanation of what this repo does, written for {username} specifically",
    "why_good_fit": "1-2 sentences explaining why this repo matches their goal of {goal} and addresses their gaps in {gaps_text}",
    "how_to_start": "3 concrete steps to make their first contribution, specific to this repo",
    "skills_they_will_learn": ["skill1", "skill2", "skill3"],
    "good_first_areas": ["area1", "area2", "area3"],
    "encouragement": "One encouraging sentence personalized to {username}"
}}

Return ONLY the JSON object, no markdown, no explanation.
"""

    def _parse_response(self, raw: str) -> dict:
        """Parse LLM JSON response."""
        import json

        # Clean up common LLM formatting issues
        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1])

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # Try to extract JSON from response
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    return json.loads(raw[start:end])
                except Exception:
                    pass

        return self._fallback_explanation("unknown", None)

    def _fallback_explanation(
        self, repo_full_name: str, gap_vector
    ) -> dict:
        """Fallback when LLM fails."""
        return {
            "summary": f"{repo_full_name} is an active open source project.",
            "why_good_fit": "This repo aligns with your contribution goals.",
            "how_to_start": "1. Read the README. 2. Look for good-first-issue labels. 3. Join their community.",
            "skills_they_will_learn": ["open source workflow", "code review", "collaboration"],
            "good_first_areas": ["documentation", "bug fixes", "tests"],
            "encouragement": "Every expert was once a beginner. You've got this!",
        }