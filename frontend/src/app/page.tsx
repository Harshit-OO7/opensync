"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function HomePage() {
  const [username, setUsername] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim()) return;
    setLoading(true);
    setError("");
    try {
      const res = await fetch(
        `https://opensync-api.onrender.com/api/v1/analyze/${username.trim()}`
      );
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "User not found");
      }
      router.push(`/onboard?username=${username.trim()}`);
    } catch (err: any) {
      setError(err.message || "Something went wrong");
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-background flex flex-col">
      <nav className="border-b border-border px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-primary" />
          <span className="text-sm font-medium text-foreground">OpenSync</span>
        </div>
      </nav>

      <div className="flex-1 flex flex-col items-center justify-center px-4 py-20">
        <div className="max-w-2xl w-full text-center space-y-8">
          <h1 className="text-5xl font-semibold tracking-tight text-foreground">
            Find OSS repos
            <br />
            <span className="text-muted-foreground">you are ready for</span>
          </h1>

          <p className="text-lg text-muted-foreground leading-relaxed max-w-lg mx-auto">
            OpenSync analyzes your GitHub activity and matches you to open
            source repositories that advance you toward your goals.
          </p>

          <form onSubmit={handleSubmit} className="max-w-md mx-auto space-y-3">
            <div className="flex gap-2">
              <input
                type="text"
                placeholder="Your GitHub username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="flex-1 bg-background border border-border rounded-lg px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground outline-none focus:border-primary transition-colors"
                disabled={loading}
              />
              <button
                type="submit"
                disabled={loading || !username.trim()}
                className="bg-primary text-primary-foreground text-sm font-medium px-4 py-2 rounded-lg hover:opacity-90 transition-opacity disabled:opacity-50"
              >
                {loading ? "Analyzing..." : "Analyze"}
              </button>
            </div>
            {error && (
              <p className="text-xs text-red-400 text-left">{error}</p>
            )}
            <p className="text-xs text-muted-foreground">
              No account needed. Just your GitHub username.
            </p>
          </form>
        </div>
      </div>
    </main>
  );
}