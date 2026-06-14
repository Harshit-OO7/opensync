"""
GitHub API client — rate-limit aware, handles pagination.
"""

import time
from dataclasses import dataclass, field
from datetime import datetime

import structlog
from github import Github, GithubException, RateLimitExceededException
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings

logger = structlog.get_logger()


@dataclass
class RawRepo:
    id: int
    full_name: str
    name: str
    description: str | None
    language: str | None
    languages: dict[str, int]
    topics: list[str]
    stars: int
    forks: int
    is_fork: bool
    created_at: datetime
    updated_at: datetime
    pushed_at: datetime | None
    has_issues: bool
    open_issues_count: int
    default_branch: str
    url: str


@dataclass
class RawCommit:
    sha: str
    message: str
    author_name: str | None
    author_email: str | None
    committed_at: datetime | None
    files_changed: int
    additions: int
    deletions: int


@dataclass
class RawPullRequest:
    number: int
    title: str
    state: str
    created_at: datetime
    merged_at: datetime | None
    closed_at: datetime | None
    body: str | None
    repo_full_name: str
    additions: int
    deletions: int
    changed_files: int
    comments: int


@dataclass
class RawGitHubProfile:
    username: str
    github_id: int
    display_name: str | None
    avatar_url: str | None
    bio: str | None
    public_repos: int
    followers: int
    following: int
    created_at: datetime
    repos: list[RawRepo] = field(default_factory=list)
    commits: list[RawCommit] = field(default_factory=list)
    pull_requests: list[RawPullRequest] = field(default_factory=list)
    fetched_at: datetime = field(default_factory=datetime.utcnow)


class GitHubClient:
    def __init__(self):
        self._github = Github(settings.GITHUB_TOKEN)
        self._log = logger.bind(service="github_client")

    def _check_rate_limit(self):
        try:
            rate_limit = self._github.get_rate_limit()
            core = rate_limit.core
            remaining = core.remaining
            reset_at = core.reset
            self._log.debug(
                "Rate limit status",
                remaining=remaining,
                reset_at=reset_at.isoformat(),
            )
            if remaining < 50:
                wait_seconds = (
                    reset_at - datetime.utcnow()
                ).total_seconds() + 5
                if wait_seconds > 0:
                    self._log.warning(
                        "Rate limit low — waiting",
                        remaining=remaining,
                        wait_seconds=wait_seconds,
                    )
                    time.sleep(wait_seconds)
        except Exception:
            pass

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True,
    )
    def fetch_profile(
        self,
        username: str,
        max_repos: int = 30,
        max_commits_per_repo: int = 50,
        max_prs: int = 50,
    ) -> RawGitHubProfile:
        self._log.info("Fetching GitHub profile", username=username)
        self._check_rate_limit()

        try:
            user = self._github.get_user(username)
        except GithubException as e:
            if e.status == 404:
                raise ValueError(f"GitHub user '{username}' not found")
            raise

        repos = self._fetch_repos(user, max_repos)
        commits = self._fetch_commits(user, repos, max_commits_per_repo)
        pull_requests = self._fetch_pull_requests(username, max_prs)

        profile = RawGitHubProfile(
            username=user.login,
            github_id=user.id,
            display_name=user.name,
            avatar_url=user.avatar_url,
            bio=user.bio,
            public_repos=user.public_repos,
            followers=user.followers,
            following=user.following,
            created_at=user.created_at,
            repos=repos,
            commits=commits,
            pull_requests=pull_requests,
        )

        self._log.info(
            "Profile fetched successfully",
            username=username,
            repos=len(repos),
            commits=len(commits),
            pull_requests=len(pull_requests),
        )

        return profile

    def _fetch_repos(self, user, max_repos: int) -> list[RawRepo]:
        self._check_rate_limit()
        repos = []

        try:
            for repo in user.get_repos(sort="pushed", type="owner"):
                if len(repos) >= max_repos:
                    break
                if repo.fork:
                    continue

                try:
                    languages = dict(repo.get_languages())
                except Exception:
                    languages = {}

                try:
                    topics = repo.get_topics()
                except Exception:
                    topics = []

                repos.append(RawRepo(
                    id=repo.id,
                    full_name=repo.full_name,
                    name=repo.name,
                    description=repo.description,
                    language=repo.language,
                    languages=languages,
                    topics=topics,
                    stars=repo.stargazers_count,
                    forks=repo.forks_count,
                    is_fork=repo.fork,
                    created_at=repo.created_at,
                    updated_at=repo.updated_at,
                    pushed_at=repo.pushed_at,
                    has_issues=repo.has_issues,
                    open_issues_count=repo.open_issues_count,
                    default_branch=repo.default_branch,
                    url=repo.html_url,
                ))

        except RateLimitExceededException:
            self._check_rate_limit()

        self._log.info("Repos fetched", count=len(repos))
        return repos

    def _fetch_commits(
        self,
        user,
        repos: list[RawRepo],
        max_per_repo: int,
    ) -> list[RawCommit]:
        self._check_rate_limit()
        all_commits = []

        for raw_repo in repos[:10]:
            try:
                repo = self._github.get_repo(raw_repo.full_name)
                commits = repo.get_commits(author=user.login)
                count = 0

                for commit in commits:
                    if count >= max_per_repo:
                        break

                    try:
                        # Safely get file and stats info
                        files_changed = 0
                        additions = 0
                        deletions = 0

                        try:
                            files_changed = sum(1 for _ in commit.files)
                        except Exception:
                            pass

                        try:
                            additions = commit.stats.additions
                            deletions = commit.stats.deletions
                        except Exception:
                            pass

                        all_commits.append(RawCommit(
                            sha=commit.sha,
                            message=commit.commit.message,
                            author_name=(
                                commit.commit.author.name
                                if commit.commit.author else None
                            ),
                            author_email=(
                                commit.commit.author.email
                                if commit.commit.author else None
                            ),
                            committed_at=(
                                commit.commit.author.date
                                if commit.commit.author else None
                            ),
                            files_changed=files_changed,
                            additions=additions,
                            deletions=deletions,
                        ))
                        count += 1

                    except GithubException:
                        continue

            except (GithubException, RateLimitExceededException):
                self._check_rate_limit()
                continue

        self._log.info("Commits fetched", count=len(all_commits))
        return all_commits

    def _fetch_pull_requests(
        self,
        username: str,
        max_prs: int,
    ) -> list[RawPullRequest]:
        self._check_rate_limit()
        pull_requests = []

        try:
            query = f"type:pr author:{username} is:public"
            results = self._github.search_issues(query)

            for pr in results:
                if len(pull_requests) >= max_prs:
                    break
                try:
                    pull_requests.append(RawPullRequest(
                        number=pr.number,
                        title=pr.title,
                        state=pr.state,
                        created_at=pr.created_at,
                        merged_at=(
                            pr.pull_request.merged_at
                            if pr.pull_request else None
                        ),
                        closed_at=pr.closed_at,
                        body=pr.body,
                        repo_full_name=pr.repository.full_name,
                        additions=0,
                        deletions=0,
                        changed_files=0,
                        comments=pr.comments,
                    ))
                except Exception:
                    continue

        except GithubException as e:
            self._log.warning("Failed to fetch PRs", error=str(e))

        self._log.info("PRs fetched", count=len(pull_requests))
        return pull_requests