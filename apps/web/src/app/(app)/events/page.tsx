import type { Metadata } from "next";
import Link from "next/link";

import { api } from "@/lib/api";
import type { CamEvent } from "@/lib/types";

import { AutoRefresh } from "./auto-refresh";
import { StateBadge } from "./state-badge";

export const metadata: Metadata = { title: "Events" };

const SEVERITY = { info: "text-accent", warning: "text-warn", critical: "text-danger" } as const;

export default async function EventsPage({ searchParams }: PageProps<"/events">) {
  const { all } = await searchParams;
  const events = await api<{ results: CamEvent[] }>(`/events?limit=60${all ? "&include_dismissed=1" : ""}`);
  return (
    <div className="space-y-6">
      <AutoRefresh seconds={4} />
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Events</h1>
          <p className="text-sm text-muted">One event per incident, with the evidence. Updates live.</p>
        </div>
        <Link href={all ? "/events" : "/events?all=1"} className="text-sm text-accent">
          {all ? "Hide dismissed" : "Show dismissed (AI said no)"}
        </Link>
      </div>
      <ul className="space-y-3">
        {events.results.map((event) => (
          <li key={event.id}>
            <Link
              href={`/events/${event.id}`}
              className="flex gap-4 rounded-xl border border-line bg-surface p-3 hover:border-accent"
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={`/bff/events/${event.id}/snapshot`}
                alt=""
                className="aspect-video w-48 shrink-0 rounded-md bg-black object-cover"
              />
              <div className="min-w-0 space-y-1">
                <p className="flex flex-wrap items-center gap-2">
                  <span className={`text-xs font-bold uppercase ${SEVERITY[event.severity]}`}>{event.severity}</span>
                  <span className="font-medium">{event.rule}</span>
                  <StateBadge event={event} />
                </p>
                <p className="text-sm">{event.reason}</p>
                <p className="text-xs text-muted">
                  {event.camera} · {new Date(event.t_start).toLocaleString("en-GB", { timeZone: "Asia/Karachi" })}
                  {event.t_end &&
                    ` · ${Math.max(0, Math.round((+new Date(event.t_end) - +new Date(event.t_start)) / 1000))} s`}
                </p>
              </div>
            </Link>
          </li>
        ))}
        {!events.results.length && <p className="text-muted">No events yet. Activate a rule and wait for it to happen.</p>}
      </ul>
    </div>
  );
}
