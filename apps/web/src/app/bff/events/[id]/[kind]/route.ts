// Event snapshots and crops, fetched with the session's token (never exposed to the browser).

import { accessToken } from "@/lib/api";
import { API_URL } from "@/lib/session";

export async function GET(_: Request, { params }: RouteContext<"/bff/events/[id]/[kind]">) {
  const { id, kind } = await params;
  if (kind !== "snapshot" && kind !== "crop") return new Response(null, { status: 404 });
  const token = await accessToken();
  if (!token) return new Response(null, { status: 401 });
  const upstream = await fetch(`${API_URL}/api/v1/events/${encodeURIComponent(id)}/${kind}.jpg`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  if (!upstream.ok) return new Response(null, { status: upstream.status });
  return new Response(upstream.body, {
    headers: { "Content-Type": "image/jpeg", "Cache-Control": "private, max-age=3600" },
  });
}
