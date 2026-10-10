import type { CamEvent } from "@/lib/types";

export function StateBadge({ event }: { event: CamEvent }) {
  if (event.state === "dismissed")
    return <span className="rounded-full bg-line px-2 py-0.5 text-xs text-muted">AI: no issue · dismissed</span>;
  if (event.state === "verifying")
    return <span className="rounded-full bg-accent/15 px-2 py-0.5 text-xs text-accent">AI checking…</span>;
  if (event.verification.answer)
    return <span className="rounded-full bg-ok/15 px-2 py-0.5 text-xs text-ok">✓ AI-verified</span>;
  if (event.state === "unverified")
    return <span className="rounded-full bg-warn/15 px-2 py-0.5 text-xs text-warn">⚠ unverified</span>;
  return <span className="rounded-full bg-ok/15 px-2 py-0.5 text-xs text-ok">confirmed</span>;
}
