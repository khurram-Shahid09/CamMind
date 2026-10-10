import type { Metadata } from "next";

import { api } from "@/lib/api";
import type { Rule, Site } from "@/lib/types";

import { setStatus } from "./actions";
import { NewRule } from "./new-rule";

export const metadata: Metadata = { title: "Rules" };

export default async function RulesPage() {
  const [rules, sites] = await Promise.all([
    api<{ results: Rule[] }>("/rules"),
    api<{ results: Site[] }>("/sites"),
  ]);
  const siteName = new Map(sites.results.map((s) => [s.id, s.name]));
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Rules</h1>
        <p className="text-sm text-muted">
          Type a rule. CamMind compiles it into a precise rule and shows what it understood before anything runs.
        </p>
      </div>
      <NewRule sites={sites.results} />
      <section className="space-y-3">
        <h2 className="font-semibold">Your rules</h2>
        {rules.results.map((rule) => (
          <article key={rule.id} className="flex items-start justify-between gap-4 rounded-xl border border-line bg-surface p-4">
            <div className="space-y-1">
              <p className="font-medium">
                {rule.name} <span className="text-sm font-normal text-muted">· {siteName.get(rule.site_id)}</span>
              </p>
              {rule.version?.source_text && <p className="text-sm text-muted">“{rule.version.source_text}”</p>}
              <p className="text-sm">{rule.version?.summary}</p>
            </div>
            <form action={setStatus.bind(null, rule.id, rule.status === "active" ? "paused" : "active")}>
              <button
                className={`rounded-full px-3 py-1 text-xs font-semibold ${
                  rule.status === "active" ? "bg-ok/15 text-ok" : "bg-line text-muted"
                }`}
              >
                {rule.status === "active" ? "● Active" : "Paused"}
              </button>
            </form>
          </article>
        ))}
      </section>
    </div>
  );
}
