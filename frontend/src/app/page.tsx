export default function HomePage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center px-4">
      <div className="max-w-2xl text-center space-y-6">
        <div className="inline-flex items-center rounded-full border border-border px-3 py-1 text-xs text-muted-foreground">
          Phase 0 — Foundation
        </div>

        <h1 className="text-4xl font-semibold tracking-tight text-foreground">
          OpenSync
        </h1>

        <p className="text-lg text-muted-foreground leading-relaxed">
          A contribution readiness engine. Discover open-source repositories
          matched to where you are and where you want to grow.
        </p>

        <p className="text-sm text-muted-foreground">
          Under active development — Phase 1 (GitHub ingestion) coming next.
        </p>
      </div>
    </main>
  );
}