import type { Metadata } from "next";
import { revalidatePath } from "next/cache";
import Link from "next/link";

import { api } from "@/lib/api";
import type { CamEvent } from "@/lib/types";

import { StateBadge } from "../state-badge";

export const metadata: Metadata = { title: "Event" };

async function feedback(id: string, verdict: "confirmed" | "false_alarm") {
  "use server";
  await api(`/events/${id}`, { method: "PATCH", body: JSON.stringify({ feedback: verdict }) });
  revalidatePath(`/events/${id}`);
}

export default async function EventPage({ params }: PageProps<"/events/[id]">) {
  const { id } = await params;
  const event = await api<CamEvent>(`/events/${id}`);
  const v = event.verification;
  return (
    <div className="space-y-6">
      <Link href="/events" className="text-sm text-accent">
        ← Events
      </Link>
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">{event.rule}</h1>
        <StateBadge event={event} />
      </div>
      <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={`/bff/events/${event.id}/snapshot`} alt="Snapshot with detections" className="w-full rounded-xl border border-line" />
        <div className="space-y-4">
          <section className="space-y-2 rounded-xl border border-line bg-surface p-4">
            <h2 className="text-xs uppercase tracking-wider text-muted">Why this fired</h2>
            <p className="font-medium">{event.reason}</p>
            <p className="text-sm text-muted">{event.summary}</p>
            <p className="text-xs text-muted">
              {event.camera} · {new Date(event.t_start).toLocaleString("en-GB", { timeZone: "Asia/Karachi" })}
            </p>
          </section>
          {(v.answer || v.error) && (
            <section className="space-y-2 rounded-xl border border-line bg-surface p-4">
              <h2 className="text-xs uppercase tracking-wider text-muted">AI check (one yes/no question on a crop)</h2>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={`/bff/events/${event.id}/crop`} alt="Crop sent to the AI" className="max-h-48 rounded-md" />
              {v.answer ? (
                <p className="text-sm">
                  Answer <b>{v.answer.toUpperCase()}</b> ({Math.round((v.confidence ?? 0) * 100)}%): “{v.reason}”
                </p>
              ) : (
                <p className="text-sm text-warn">{v.error}</p>
              )}
              <p className="text-xs text-muted">The AI only answers the question. Rules decide what happens.</p>
            </section>
          )}
          <section className="flex gap-2">
            {event.feedback ? (
              <p className="text-sm text-muted">
                Marked as {event.feedback === "confirmed" ? "confirmed ✓" : "false alarm ✗"}
              </p>
            ) : (
              <>
                <form action={feedback.bind(null, event.id, "confirmed")}>
                  <button className="rounded-md bg-ok/15 px-3 py-2 text-sm text-ok">Confirm</button>
                </form>
                <form action={feedback.bind(null, event.id, "false_alarm")}>
                  <button className="rounded-md bg-danger/15 px-3 py-2 text-sm text-danger">False alarm</button>
                </form>
              </>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
