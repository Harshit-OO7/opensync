"""
Repository indexer.

Fetches curated OSS repositories from GitHub, scores their
newcomer friendliness, and stores them in PostgreSQL + Qdrant.
"""

import uuid
from datetime import datetime, timezone

import structlog
from github import Github
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from sentence_transformers import SentenceTransformer
from sqlalchemy import text

from app.core.config import settings
from app.db.session import AsyncSessionLocal

logger = structlog.get_logger()

# ── Curated list of beginner-friendly OSS repos by domain ────────────────────
CURATED_REPOS = {
    "ai-ml-tooling": [
        "huggingface/datasets",
        "huggingface/tokenizers",
        "lightning-AI/pytorch-lightning",
        "scikit-learn/scikit-learn",
        "explosion/spaCy",
        "pydantic/pydantic-ai",
        "langchain-ai/langchain",
        "openai/openai-python",
    ],
    "web-frontend": [
        "shadcn-ui/ui",
        "tailwindlabs/tailwindcss",
        "vercel/next.js",
        "facebook/react",
        "vitejs/vite",
        "vuejs/vue",
    ],
    "web-backend": [
        "tiangolo/fastapi",
        "django/django",
        "pallets/flask",
        "expressjs/express",
        "nestjs/nest",
        "gin-gonic/gin",
    ],
    "developer-tooling": [
        "microsoft/vscode",
        "astral-sh/ruff",
        "prettier/prettier",
        "eslint/eslint",
        "biomejs/biome",
        "cli/cli",
    ],
    "web-infrastructure": [
        "traefik/traefik",
        "nginx/nginx",
        "containerd/containerd",
        "grafana/grafana",
        "prometheus/prometheus",
    ],
    "data-engineering": [
        "apache/airflow",
        "great-expectations/great_expectations",
        "dbt-labs/dbt-core",
        "dagster-io/dagster",
    ],
    "systems-programming": [
        "rust-lang/rust",
        "tokio-rs/tokio",
        "denoland/deno",
        "golang/go",
    ],
    "security": [
        "aquasecurity/trivy",
        "anchore/syft",
        "gitleaks/gitleaks",
    ],
    "mobile": [
        "flutter/flutter",
        "facebook/react-native",
        "ionic-team/ionic-framework",
    ],
    "documentation": [
        "facebook/docusaurus",
        "squidfunk/mkdocs-material",
        "withastro/astro",
    ],
}


class RepoIndexer:
    """
    Fetches, scores, and indexes OSS repositories.

    Usage:
        indexer = RepoIndexer()
        await indexer.index_all()
    """

    COLLECTION_NAME = "repositories"
    VECTOR_SIZE = 384  # all-MiniLM-L6-v2 output dim

    def __init__(self):
        self._log = logger.bind(service="repo_indexer")
        self._github = Github(settings.GITHUB_TOKEN)
        self._qdrant = QdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT,
        )
        self._model = SentenceTransformer(settings.EMBEDDING_MODEL)
        self._ensure_collection()

    def _ensure_collection(self):
        """Create Qdrant collection if it doesn't exist."""
        collections = self._qdrant.get_collections().collections
        names = [c.name for c in collections]

        if self.COLLECTION_NAME not in names:
            self._qdrant.create_collection(
                collection_name=self.COLLECTION_NAME,
                vectors_config=VectorParams(
                    size=self.VECTOR_SIZE,
                    distance=Distance.COSINE,
                ),
            )
            self._log.info("Created Qdrant collection", name=self.COLLECTION_NAME)

    def _build_repo_text(self, repo) -> str:
        """Build text representation of a repo for embedding."""
        parts = [
            repo.full_name.replace("/", " ").replace("-", " "),
            repo.description or "",
            " ".join(repo.get_topics()),
            repo.language or "",
        ]
        return " ".join(filter(None, parts))

    def _score_newcomer_friendliness(self, repo) -> float:
        """Score how friendly a repo is for new contributors (0-1)."""
        score = 0.0

        # Has contributing guide
        try:
            repo.get_contents("CONTRIBUTING.md")
            score += 0.3
        except Exception:
            try:
                repo.get_contents(".github/CONTRIBUTING.md")
                score += 0.3
            except Exception:
                pass

        # Has code of conduct
        try:
            repo.get_contents("CODE_OF_CONDUCT.md")
            score += 0.1
        except Exception:
            pass

        # Has good first issue label
        labels = [l.name.lower() for l in repo.get_labels()]
        if any("good first" in l for l in labels):
            score += 0.3

        # Active repo (pushed within 90 days)
        if repo.pushed_at:
            days_since = (
                datetime.now(timezone.utc) - repo.pushed_at.replace(
                    tzinfo=timezone.utc
                )
            ).days
            if days_since < 90:
                score += 0.2
            elif days_since < 180:
                score += 0.1

        # Has issues enabled
        if repo.has_issues and repo.open_issues_count > 0:
            score += 0.1

        return round(min(score, 1.0), 3)

    async def index_all(self, domains: list[str] | None = None):
        """
        Index all curated repositories.

        Args:
            domains: List of domains to index. If None, indexes all.
        """
        target_domains = domains or list(CURATED_REPOS.keys())
        total_indexed = 0

        for domain in target_domains:
            repos = CURATED_REPOS.get(domain, [])
            self._log.info(
                "Indexing domain",
                domain=domain,
                repo_count=len(repos),
            )

            for repo_name in repos:
                try:
                    indexed = await self._index_repo(repo_name, domain)
                    if indexed:
                        total_indexed += 1
                except Exception as e:
                    self._log.error(
                        "Failed to index repo",
                        repo=repo_name,
                        error=str(e),
                    )
                    continue

        self._log.info("Indexing complete", total_indexed=total_indexed)
        return total_indexed

    async def _index_repo(self, repo_name: str, domain: str) -> bool:
        """Fetch, score, embed, and store a single repository."""
        self._log.info("Indexing repo", repo=repo_name)

        try:
            repo = self._github.get_repo(repo_name)
        except Exception as e:
            self._log.warning("Repo not found", repo=repo_name, error=str(e))
            return False

        # Score newcomer friendliness
        friendliness = self._score_newcomer_friendliness(repo)

        # Build embedding text and embed
        repo_text = self._build_repo_text(repo)
        embedding = self._model.encode(repo_text).tolist()

        # Generate ID
        repo_id = str(uuid.uuid4())
        embedding_id = str(uuid.uuid4())

        # Store in PostgreSQL
        async with AsyncSessionLocal() as session:
            async with session.begin():
                await session.execute(
                    text("""
                        INSERT INTO repositories (
                            id, github_id, full_name, description,
                            primary_language, topics, stars, forks,
                            open_issues, last_commit_at,
                            has_contributing_guide, newcomer_friendliness,
                            embedding_id, last_indexed_at,
                            created_at, updated_at
                        ) VALUES (
                            :id, :github_id, :full_name, :description,
                            :language, :topics, :stars, :forks,
                            :open_issues, :last_commit_at,
                            :has_contributing, :friendliness,
                            :embedding_id, now(), now(), now()
                        )
                        ON CONFLICT (github_id) DO UPDATE SET
                            description = EXCLUDED.description,
                            stars = EXCLUDED.stars,
                            forks = EXCLUDED.forks,
                            open_issues = EXCLUDED.open_issues,
                            newcomer_friendliness = EXCLUDED.newcomer_friendliness,
                            embedding_id = EXCLUDED.embedding_id,
                            last_indexed_at = now(),
                            updated_at = now()
                    """),
                    {
                        "id": repo_id,
                        "github_id": repo.id,
                        "full_name": repo.full_name,
                        "description": repo.description,
                        "language": repo.language,
                        "topics": repo.get_topics(),
                        "stars": repo.stargazers_count,
                        "forks": repo.forks_count,
                        "open_issues": repo.open_issues_count,
                        "last_commit_at": repo.pushed_at,
                        "has_contributing": False,
                        "friendliness": friendliness,
                        "embedding_id": embedding_id,
                    },
                )

        # Store embedding in Qdrant
        self._qdrant.upsert(
            collection_name=self.COLLECTION_NAME,
            points=[
                PointStruct(
                    id=embedding_id,
                    vector=embedding,
                    payload={
                        "full_name": repo.full_name,
                        "description": repo.description or "",
                        "language": repo.language or "",
                        "topics": repo.get_topics(),
                        "domain": domain,
                        "stars": repo.stargazers_count,
                        "newcomer_friendliness": friendliness,
                        "db_id": repo_id,
                    },
                )
            ],
        )

        self._log.info(
            "Repo indexed",
            repo=repo_name,
            friendliness=friendliness,
        )
        return True