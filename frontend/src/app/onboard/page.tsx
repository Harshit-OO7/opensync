"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api, Domain } from "@/lib/api";
import { ArrowRight, Loader2 } from "lucide-react";

export const dynamic = "force-dynamic";
export default function OnboardPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const username = searchParams.get("username") || "";

  const [domains, setDomains] = useState<Domain[]>([]);
  const [selected, setSelected] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!username) {
      router.push("/");
      return;
    }
    api
      .getDomains()
      .then(setDomains)
      .finally(() => setLoading(false));
  }, [username, router]);

  const handleContinue = () => {
    if (!selected) return;
    setSubmitting(true);
    router.push(`/dashboard?username=${username}&goal=${selected}`);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <Loader2 className="animate-spin text-muted-foreground" size={24} />
      </div>
    );
  }

  return (
    <main className="min-h-screen bg-background flex flex-col items-center justify-center px-4 py-12">
      <div className="max-w-2xl w-full space-y-8">
        {/* Header */}
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-primary" />
            <span className="text-xs text-muted-foreground">OpenSync</span>
          </div>
          <h1 className="text-2xl font-semibold text-foreground">
            What do you want to contribute to?
          </h1>
          <p className="text-sm text-muted-foreground">
            Hey{" "}
            <span className="text-foreground font-medium">{username}</span> —
            pick your goal and we&apos;ll find repos that match your skill gaps.
          </p>
        </div>

        {/* Domain grid */}
        <div className="grid grid-cols-2 gap-3">
          {domains.map((domain) => (
            <button
              key={domain.domain}
              onClick={() => setSelected(domain.domain)}
              className={`text-left p-4 rounded-lg border transition-all ${
                selected === domain.domain
                  ? "border-primary bg-primary/5"
                  : "border-border hover:border-border/80 bg-background"
              }`}
            >
              <div className="text-sm font-medium text-foreground">
                {domain.display_name}
              </div>
              <div className="text-xs text-muted-foreground mt-1 line-clamp-2">
                {domain.description}
              </div>
            </button>
          ))}
        </div>

        {/* Continue */}
        <button
          onClick={handleContinue}
          disabled={!selected || submitting}
          className="w-full flex items-center justify-center gap-2 bg-primary text-primary-foreground text-sm font-medium px-4 py-3 rounded-lg hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {submitting ? (
            <Loader2 size={16} className="animate-spin" />
          ) : (
            <>
              Continue to Dashboard
              <ArrowRight size={14} />
            </>
          )}
        </button>
      </div>
    </main>
  );
}