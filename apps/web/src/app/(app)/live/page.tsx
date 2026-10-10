import type { Metadata } from "next";

import { api } from "@/lib/api";
import type { Camera, Rule, Site } from "@/lib/types";

import { LiveTile } from "./live-tile";

export const metadata: Metadata = { title: "Live" };

export default async function LivePage() {
  const [cameras, sites, rules] = await Promise.all([
    api<{ results: Camera[] }>("/cameras"),
    api<{ results: Site[] }>("/sites"),
    api<{ results: Rule[] }>("/rules"),
  ]);
  const siteName = new Map(sites.results.map((s) => [s.id, s.name]));
  const watching = new Map<string, number>();
  for (const rule of rules.results) {
    if (rule.status !== "active") continue;
    for (const id of (rule.version?.spec.camera_ids as string[] | undefined) ?? []) {
      watching.set(id, (watching.get(id) ?? 0) + 1);
    }
  }
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Live</h1>
        <p className="text-sm text-muted">
          {cameras.results.length} cameras · video stays on this machine (go2rtc)
        </p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {cameras.results.map((camera) => {
          const rulesOn = watching.get(camera.id) ?? 0;
          return (
            <figure key={camera.id} className="overflow-hidden rounded-xl border border-line bg-surface">
              <div className="relative aspect-video bg-black">
                {/* Frames come straight from go2rtc on this machine; the dashboard never proxies video. */}
                <LiveTile cameraId={camera.id} name={camera.name} />
                <span className="absolute left-2 top-2 flex items-center gap-1.5 rounded bg-black/60 px-2 py-0.5 text-xs text-white">
                  <span className="h-2 w-2 rounded-full bg-ok" /> LIVE
                </span>
              </div>
              <figcaption className="flex items-center justify-between px-3 py-2 text-sm">
                <span>
                  <span className="font-medium">{camera.name}</span>
                  <span className="text-muted"> · {siteName.get(camera.site_id)}</span>
                </span>
                <span className={rulesOn ? "text-accent" : "text-muted"}>
                  {rulesOn ? `${rulesOn} rule${rulesOn > 1 ? "s" : ""} watching` : "no rules"}
                </span>
              </figcaption>
            </figure>
          );
        })}
      </div>
    </div>
  );
}
