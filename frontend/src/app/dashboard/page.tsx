"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api, SkillProfile, GapVector, RecommendationResult, RepoGuide } from "@/lib/api";
import {
  Loader2, Github, Star, ExternalLink, ChevronRight,
  BookOpen, Zap, Target, CheckCircle, AlertCircle
} from "lucide-react";

export const dynamic = "force-dynamic";
export default function DashboardPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const username = searchParams.get("username") || "";
  const goal = searchParams.get("goal") || "";

  const [profile, setProfile] = useState<SkillProfile | null>(null);
  const [gap, setGap] = useState<GapVector | null>(null);
  const [recommendations, setRecommendations] = useState<RecommendationResult | null>(null);
  const [selectedRepo, setSelectedRepo] = useState<string | null>(null);
  const [repoGuide, setRepoGuide] = useState<RepoGuide | null>(null);
  const [loadingGuide, setLoadingGuide] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState<"overview" | "recommendations" | "guide">("overview");

  useEffect(() => {
    if (!username || !goal) {
      router.push("/");
      return;
    }
    loadData();
  }, [username, goal]);

  const loadData = async () => {
    try {
      setLoading(true);
      const [profileData, gapData, recsData] = await Promise.all([
        api.analyze(username),
        api.getGap(username, goal),
        api.getRecommendations(username, goal, 5),
      ]);
      setProfile(profileData);
      setGap(gapData);
      setRecommendations(recsData);
    } catch (err: any) {
      setError(err.message || "Failed to load data");
    } finally {
      setLoading(false);
    }
  };

  const handleGetGuide = async (repoName: string) => {
    setSelectedRepo(repoName);
    setLoadingGuide(true);
    setActiveTab("guide");
    try {
      const guideData = await api.getRepoGuide(username, repoName, goal);
      setRepoGuide(guideData);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoadingGuide(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex flex-col items-center justify-center gap-3">
        <Loader2 className="animate-spin text-primary" size={24} />
        <p className="text-sm text-muted-foreground">Analyzing your GitHub profile...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center space-y-3">
          <p className="text-sm text-red-400">{error}</p>
          <button
            onClick={() => router.push("/")}
            className="text-xs text-muted-foreground hover:text-foreground"
          >
            Go back
          </button>
        </div>
      </div>
    );
  }

  let skillData: { skill: string; value: number }[] = [];
  if (profile) {
    skillData = Object.entries(profile.language_signals.language_distribution)
      .filter((entry) => entry[1] > 0.02)
      .slice(0, 6)
      .map((entry) => ({ skill: entry[0], value: Math.round(entry[1] * 100) }));
  }

  return (
    <div className="min-h-screen bg-background">
      <nav className="border-b border-border px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-primary" />
          <span className="text-sm font-medium">OpenSync</span>
        </div>
        <div className="flex items-center gap-3">
          {profile?.avatar_url && (
            <img src={profile.avatar_url} alt={username} className="w-6 h-6 rounded-full" />
          )}
          <span className="text-xs text-muted-foreground">{username}</span>
          <span className="text-xs px-2 py-0.5 rounded-full bg-primary/10 text-primary border border-primary/20">
            {gap?.goal_display_name}
          </span>
        </div>
      </nav>

      <div className="flex h-[calc(100vh-49px)]">
        <aside className="w-48 border-r border-border flex flex-col p-3 gap-1 flex-shrink-0">
          {[
            { id: "overview", label: "Overview", icon: <Zap size={14} /> },
            { id: "recommendations", label: "Repos", icon: <Target size={14} /> },
            { id: "guide", label: "AI Guide", icon: <BookOpen size={14} /> },
          ].map((item) => (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id as any)}
              className={`flex items-center gap-2 px-3 py-2 rounded-md text-xs transition-colors text-left ${
                activeTab === item.id
                  ? "bg-secondary text-foreground font-medium"
                  : "text-muted-foreground hover:text-foreground hover:bg-secondary/50"
              }`}
            >
              {item.icon}
              {item.label}
            </button>
          ))}
        </aside>

        <main className="flex-1 overflow-y-auto p-6">
          {activeTab === "overview" && (
            <div className="space-y-6 max-w-4xl">
              <div>
                <h1 className="text-lg font-semibold text-foreground">Your skill profile</h1>
                <p className="text-xs text-muted-foreground mt-1">{gap?.message}</p>
              </div>

              <div className="grid grid-cols-4 gap-3">
                {[
                  {
                    label: "Profile confidence",
                    value: `${Math.round((profile?.profile_confidence || 0) * 100)}%`,
                    sub: "based on GitHub data",
                  },
                  {
                    label: "Readiness score",
                    value: `${Math.round((gap?.readiness_score || 0) * 100)}%`,
                    sub: `for ${gap?.goal_display_name}`,
                  },
                  {
                    label: "Commits analyzed",
                    value: profile?.commit_quality.total_commits || 0,
                    sub: "across your repos",
                  },
                  {
                    label: "Repos matched",
                    value: recommendations?.total_found || 0,
                    sub: "in your goal domain",
                  },
                ].map((m) => (
                  <div key={m.label} className="border border-border rounded-lg p-4 space-y-1">
                    <div className="text-2xl font-semibold text-foreground">{m.value}</div>
                    <div className="text-xs font-medium text-foreground">{m.label}</div>
                    <div className="text-xs text-muted-foreground">{m.sub}</div>
                  </div>
                ))}
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="border border-border rounded-lg p-4 space-y-3">
                  <h2 className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                    Language distribution
                  </h2>
                  <div className="space-y-2">
                    {skillData.map((s) => (
                      <div key={s.skill} className="flex items-center gap-2">
                        <span className="text-xs text-foreground w-24 truncate">{s.skill}</span>
                        <div className="flex-1 h-1.5 bg-secondary rounded-full overflow-hidden">
                          <div
                            className="h-full bg-primary rounded-full"
                            style={{ width: `${s.value}%` }}
                          />
                        </div>
                        <span className="text-xs text-muted-foreground w-8 text-right">
                          {s.value}%
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="border border-border rounded-lg p-4 space-y-3">
                  <h2 className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                    Gap to goal — {gap?.goal_display_name}
                  </h2>
                  <div className="space-y-2">
                    {gap?.satisfied.map((s) => (
                      <div key={s.skill_key} className="flex items-center gap-2">
                        <CheckCircle size={12} className="text-green-500 flex-shrink-0" />
                        <span className="text-xs text-foreground flex-1 truncate">
                          {s.skill_key.replace(".", " › ")}
                        </span>
                        <span className="text-xs text-green-500">✓</span>
                      </div>
                    ))}
                    {gap?.gaps.slice(0, 5).map((g) => (
                      <div key={g.skill_key} className="flex items-center gap-2">
                        <AlertCircle
                          size={12}
                          className={`flex-shrink-0 ${
                            g.priority === "high"
                              ? "text-red-400"
                              : g.priority === "medium"
                              ? "text-yellow-400"
                              : "text-muted-foreground"
                          }`}
                        />
                        <span className="text-xs text-foreground flex-1 truncate">
                          {g.skill_key.replace(".", " › ")}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          -{Math.round(g.gap_size * 100)}%
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              <div className="border border-border rounded-lg p-4 space-y-3">
                <h2 className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                  Commit quality signals
                </h2>
                <div className="grid grid-cols-4 gap-4">
                  {[
                    {
                      label: "Quality score",
                      value: Math.round((profile?.commit_quality.quality_score || 0) * 100) + "%",
                    },
                    {
                      label: "Imperative mood",
                      value:
                        Math.round((profile?.commit_quality.imperative_mood_ratio || 0) * 100) + "%",
                    },
                    {
                      label: "Atomic commits",
                      value: Math.round((profile?.commit_quality.atomic_ratio || 0) * 100) + "%",
                    },
                    {
                      label: "Generic messages",
                      value: Math.round((profile?.commit_quality.generic_ratio || 0) * 100) + "%",
                    },
                  ].map((m) => (
                    <div key={m.label} className="space-y-1">
                      <div className="text-lg font-semibold text-foreground">{m.value}</div>
                      <div className="text-xs text-muted-foreground">{m.label}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {activeTab === "recommendations" && (
            <div className="space-y-4 max-w-3xl">
              <div>
                <h1 className="text-lg font-semibold text-foreground">Repository matches</h1>
                <p className="text-xs text-muted-foreground mt-1">
                  Ranked by how well they address your skill gaps for {gap?.goal_display_name}
                </p>
              </div>
              {recommendations?.recommendations.map((repo, i) => (
                <div
                  key={repo.full_name}
                  className="border border-border rounded-lg p-4 space-y-3 hover:border-border/60 transition-colors"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="space-y-1 flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-muted-foreground">#{i + 1}</span>
                        <a
                          href={`https://github.com/${repo.full_name}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-sm font-medium text-primary hover:underline flex items-center gap-1"
                        >
                          <Github size={12} />
                          {repo.full_name}
                          <ExternalLink size={10} />
                        </a>
                      </div>
                      <p className="text-xs text-muted-foreground line-clamp-2">{repo.description}</p>
                    </div>
                    <div className="flex flex-col items-end gap-1 flex-shrink-0">
                      <span className="text-xs px-2 py-0.5 rounded-full bg-primary/10 text-primary border border-primary/20">
                        {Math.round(repo.relevance_score * 100)}% match
                      </span>
                      <div className="flex items-center gap-1 text-xs text-muted-foreground">
                        <Star size={10} />
                        {repo.stars.toLocaleString()}
                      </div>
                    </div>
                  </div>
                  <p className="text-xs text-muted-foreground border-t border-border pt-3">
                    {repo.explanation}
                  </p>
                  <div className="flex items-center justify-between">
                    <div className="flex gap-1 flex-wrap">
                      {repo.topics.slice(0, 3).map((t) => (
                        <span
                          key={t}
                          className="text-xs px-1.5 py-0.5 rounded bg-secondary text-muted-foreground"
                        >
                          {t}
                        </span>
                      ))}
                      {repo.language && (
                        <span className="text-xs px-1.5 py-0.5 rounded bg-secondary text-muted-foreground">
                          {repo.language}
                        </span>
                      )}
                    </div>
                    <button
                      onClick={() => handleGetGuide(repo.full_name)}
                      className="flex items-center gap-1 text-xs text-primary hover:underline"
                    >
                      AI Guide
                      <ChevronRight size={12} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}

          {activeTab === "guide" && (
            <div className="space-y-4 max-w-2xl">
              <div>
                <h1 className="text-lg font-semibold text-foreground">AI Repository Guide</h1>
                <p className="text-xs text-muted-foreground mt-1">
                  {selectedRepo
                    ? `Personalized explanation of ${selectedRepo}`
                    : "Select a repo from the Repos tab"}
                </p>
              </div>
              {!selectedRepo && (
                <div className="border border-border rounded-lg p-8 text-center space-y-3">
                  <BookOpen size={24} className="text-muted-foreground mx-auto" />
                  <p className="text-sm text-muted-foreground">
                    Go to the{" "}
                    <button
                      onClick={() => setActiveTab("recommendations")}
                      className="text-primary hover:underline"
                    >
                      Repos tab
                    </button>{" "}
                    and click AI Guide on any recommendation.
                  </p>
                </div>
              )}
              {loadingGuide && (
                <div className="border border-border rounded-lg p-8 flex flex-col items-center gap-3">
                  <Loader2 size={24} className="animate-spin text-primary" />
                  <p className="text-xs text-muted-foreground">Generating personalized guide...</p>
                </div>
              )}
              {repoGuide && !loadingGuide && (
                <div className="space-y-4">
                  {[
                    { label: "What is this repo?", content: repoGuide.summary },
                    { label: "Why it fits your goal", content: repoGuide.why_good_fit },
                    { label: "How to get started", content: repoGuide.how_to_start },
                  ].map((section) => (
                    <div key={section.label} className="border border-border rounded-lg p-4 space-y-2">
                      <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                        {section.label}
                      </h3>
                      <p className="text-sm text-foreground leading-relaxed">{section.content}</p>
                    </div>
                  ))}
                  <div className="grid grid-cols-2 gap-4">
                    <div className="border border-border rounded-lg p-4 space-y-2">
                      <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                        Skills you will learn
                      </h3>
                      <ul className="space-y-1">
                        {repoGuide.skills_they_will_learn.map((s) => (
                          <li key={s} className="text-xs text-foreground flex items-center gap-2">
                            <div className="w-1 h-1 rounded-full bg-primary" />
                            {s}
                          </li>
                        ))}
                      </ul>
                    </div>
                    <div className="border border-border rounded-lg p-4 space-y-2">
                      <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                        Good first areas
                      </h3>
                      <ul className="space-y-1">
                        {repoGuide.good_first_areas.map((a) => (
                          <li key={a} className="text-xs text-foreground flex items-center gap-2">
                            <div className="w-1 h-1 rounded-full bg-primary" />
                            {a}
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                  <div className="border border-primary/20 bg-primary/5 rounded-lg p-4">
                    <p className="text-sm text-foreground italic">{repoGuide.encouragement}</p>
                  </div>
                  <a
                    href={`https://github.com/${selectedRepo}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center justify-center gap-2 w-full border border-border rounded-lg py-3 text-sm text-foreground hover:bg-secondary transition-colors"
                  >
                    <Github size={14} />
                    Open {selectedRepo} on GitHub
                    <ExternalLink size={12} />
                  </a>
                </div>
              )}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}