"""
Target profiles for each goal domain.

Each profile represents the skill graph of a developer who has
successfully contributed to that domain. Used to compute gap vectors.

Initially hand-crafted based on domain knowledge.
Calibrated against contribution outcome data in Phase 6.
"""

from dataclasses import dataclass, field


@dataclass
class TargetProfile:
    """
    Skill requirements for a contribution goal domain.

    required: skills needed to make meaningful contributions
    helpful: skills that improve contribution quality
    stretch: advanced skills to grow toward
    """
    domain: str
    display_name: str
    description: str
    required: dict[str, float] = field(default_factory=dict)
    helpful: dict[str, float] = field(default_factory=dict)
    stretch: dict[str, float] = field(default_factory=dict)


# ── Target profiles for each goal domain ─────────────────────────────────────

TARGET_PROFILES: dict[str, TargetProfile] = {
    "ai-ml-tooling": TargetProfile(
        domain="ai-ml-tooling",
        display_name="AI / ML Tooling",
        description="Contribute to machine learning libraries, frameworks, and tools",
        required={
            "language.python": 0.7,
            "practice.testing": 0.6,
            "practice.clean-commits": 0.5,
        },
        helpful={
            "domain.ml": 0.5,
            "tooling.docker": 0.4,
            "practice.ci-cd": 0.4,
        },
        stretch={
            "language.rust": 0.3,
            "domain.infrastructure": 0.3,
        },
    ),

    "web-infrastructure": TargetProfile(
        domain="web-infrastructure",
        display_name="Web Infrastructure",
        description="Contribute to web servers, proxies, CDNs, and infrastructure tools",
        required={
            "language.go": 0.6,
            "domain.infrastructure": 0.6,
            "practice.clean-commits": 0.5,
        },
        helpful={
            "tooling.docker": 0.6,
            "tooling.kubernetes": 0.5,
            "language.python": 0.4,
        },
        stretch={
            "language.rust": 0.4,
            "domain.systems": 0.4,
        },
    ),

    "developer-tooling": TargetProfile(
        domain="developer-tooling",
        display_name="Developer Tooling",
        description="Contribute to CLIs, editors, build tools, and developer experience",
        required={
            "practice.clean-commits": 0.6,
            "practice.testing": 0.5,
            "language.typescript": 0.5,
        },
        helpful={
            "language.python": 0.4,
            "language.rust": 0.3,
            "practice.ci-cd": 0.4,
        },
        stretch={
            "domain.systems": 0.3,
            "language.go": 0.3,
        },
    ),

    "web-frontend": TargetProfile(
        domain="web-frontend",
        display_name="Web Frontend",
        description="Contribute to UI libraries, design systems, and frontend frameworks",
        required={
            "language.typescript": 0.7,
            "framework.react": 0.6,
            "practice.clean-commits": 0.5,
        },
        helpful={
            "language.javascript": 0.6,
            "practice.testing": 0.5,
            "practice.ci-cd": 0.3,
        },
        stretch={
            "domain.web-backend": 0.3,
            "tooling.docker": 0.3,
        },
    ),

    "web-backend": TargetProfile(
        domain="web-backend",
        display_name="Web Backend",
        description="Contribute to APIs, databases, and server-side frameworks",
        required={
            "domain.web-backend": 0.6,
            "practice.testing": 0.6,
            "practice.clean-commits": 0.5,
        },
        helpful={
            "language.python": 0.5,
            "language.go": 0.4,
            "tooling.docker": 0.4,
        },
        stretch={
            "domain.infrastructure": 0.3,
            "tooling.kubernetes": 0.3,
        },
    ),

    "data-engineering": TargetProfile(
        domain="data-engineering",
        display_name="Data Engineering",
        description="Contribute to data pipelines, ETL tools, and analytics platforms",
        required={
            "language.python": 0.7,
            "domain.data": 0.5,
            "practice.testing": 0.5,
        },
        helpful={
            "tooling.docker": 0.5,
            "domain.infrastructure": 0.4,
            "practice.ci-cd": 0.4,
        },
        stretch={
            "language.java": 0.3,
            "language.scala": 0.3,
        },
    ),

    "systems-programming": TargetProfile(
        domain="systems-programming",
        display_name="Systems Programming",
        description="Contribute to operating systems, runtimes, compilers, and low-level tools",
        required={
            "language.rust": 0.6,
            "practice.clean-commits": 0.6,
            "practice.testing": 0.5,
        },
        helpful={
            "language.cpp": 0.5,
            "language.go": 0.4,
            "domain.infrastructure": 0.4,
        },
        stretch={
            "language.c": 0.4,
            "domain.systems": 0.5,
        },
    ),

    "security": TargetProfile(
        domain="security",
        display_name="Security",
        description="Contribute to security tools, vulnerability scanners, and crypto libraries",
        required={
            "practice.clean-commits": 0.7,
            "practice.testing": 0.6,
            "language.python": 0.5,
        },
        helpful={
            "language.rust": 0.4,
            "language.go": 0.4,
            "domain.infrastructure": 0.3,
        },
        stretch={
            "language.cpp": 0.3,
            "domain.systems": 0.3,
        },
    ),

    "mobile": TargetProfile(
        domain="mobile",
        display_name="Mobile Development",
        description="Contribute to mobile frameworks, SDKs, and cross-platform tools",
        required={
            "practice.clean-commits": 0.5,
            "practice.testing": 0.5,
        },
        helpful={
            "language.typescript": 0.5,
            "language.kotlin": 0.4,
            "language.swift": 0.4,
        },
        stretch={
            "language.rust": 0.3,
            "domain.systems": 0.3,
        },
    ),

    "documentation": TargetProfile(
        domain="documentation",
        display_name="Documentation & Education",
        description="Contribute to docs, tutorials, and educational content",
        required={
            "practice.clean-commits": 0.5,
            "practice.open-source-contribution": 0.3,
        },
        helpful={
            "language.python": 0.3,
            "language.javascript": 0.3,
            "language.typescript": 0.3,
        },
        stretch={
            "practice.ci-cd": 0.3,
            "practice.testing": 0.4,
        },
    ),
}


def get_profile(domain: str) -> TargetProfile | None:
    """Get target profile for a domain. Returns None if not found."""
    return TARGET_PROFILES.get(domain)


def list_domains() -> list[dict]:
    """List all available goal domains."""
    return [
        {
            "domain": profile.domain,
            "display_name": profile.display_name,
            "description": profile.description,
        }
        for profile in TARGET_PROFILES.values()
    ]