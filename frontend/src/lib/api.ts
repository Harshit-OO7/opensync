/**
 * OpenSync API client.
 * All backend calls go through here.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface SkillProfile {
  developer_id: string;
  github_username: string;
  display_name: string | null;
  avatar_url: string | null;
  account_age_days: number;
  total_public_repos: number;
  profile_confidence: number;
  commit_quality: {
    total_commits: number;
    quality_score: number;
    generic_ratio: number;
    imperative_mood_ratio: number;
    atomic_ratio: number;
    avg_message_length: number;
  };
  repo_quality: {
    total_repos: number;
    quality_score: number;
    has_tests_ratio: number;
    has_ci_ratio: number;
    avg_stars: number;
  };
  language_signals: {
    primary_language: string | null;
    language_distribution: Record<string, number>;
    detected_frameworks: string[];
    detected_domains: string[];
    detected_tooling: string[];
  };
  collaboration: {
    total_prs: number;
    merged_pr_ratio: number;
    avg_pr_comments: number;
    contributes_to_others: boolean;
  };
  analyzed_at: string;
}

export interface SkillGap {
  skill_key: string;
  category: string;
  required_confidence: number;
  current_confidence: number;
  gap_size: number;
  priority: string;
}

export interface GapVector {
  developer_id: string;
  github_username: string;
  goal_domain: string;
  goal_display_name: string;
  readiness_score: number;
  top_priorities: string[];
  gaps: SkillGap[];
  satisfied: SkillGap[];
  computed_at: string;
  message: string;
}

export interface RepoRecommendation {
  full_name: string;
  description: string;
  language: string;
  topics: string[];
  stars: number;
  newcomer_friendliness: number;
  relevance_score: number;
  matched_gaps: string[];
  explanation: string;
}

export interface RecommendationResult {
  github_username: string;
  goal_domain: string;
  goal_display_name: string;
  readiness_score: number;
  recommendations: RepoRecommendation[];
  total_found: number;
  generated_at: string;
}

export interface RepoGuide {
  repo_full_name: string;
  github_username: string;
  goal_domain: string;
  summary: string;
  why_good_fit: string;
  how_to_start: string;
  skills_they_will_learn: string[];
  good_first_areas: string[];
  encouragement: string;
}

export interface Domain {
  domain: string;
  display_name: string;
  description: string;
}

async function fetchAPI<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`);
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(error.detail || `API error: ${res.status}`);
  }
  return res.json();
}

export const api = {
  analyze: (username: string): Promise<SkillProfile> =>
    fetchAPI(`/api/v1/analyze/${username}`),

  getDomains: (): Promise<Domain[]> =>
    fetchAPI("/api/v1/gap/domains"),

  getGap: (username: string, goal: string): Promise<GapVector> =>
    fetchAPI(`/api/v1/gap/${username}?goal=${goal}`),

  getRecommendations: (
    username: string,
    goal: string,
    topK = 5
  ): Promise<RecommendationResult> =>
    fetchAPI(
      `/api/v1/recommendations/${username}?goal=${goal}&top_k=${topK}`
    ),

  getRepoGuide: (
    username: string,
    repo: string,
    goal: string
  ): Promise<RepoGuide> =>
    fetchAPI(
      `/api/v1/guide/${username}?repo=${encodeURIComponent(repo)}&goal=${goal}`
    ),
};