"use server";

import { revalidatePath } from "next/cache";

import { ApiError, api } from "@/lib/api";
import type { Compiled } from "@/lib/types";

export async function compileRule(text: string, siteId: string): Promise<Compiled> {
  try {
    return await api<Compiled>("/rules/compile", {
      method: "POST",
      body: JSON.stringify({ text, site_id: siteId }),
    });
  } catch (error) {
    return { kind: "error", errors: [error instanceof ApiError ? error.message : "Something went wrong."] };
  }
}

export async function activateRule(
  siteId: string,
  name: string,
  text: string,
  spec: Record<string, unknown>,
  assumptions: string[],
): Promise<string | null> {
  try {
    await api("/rules", {
      method: "POST",
      body: JSON.stringify({ site_id: siteId, name, source_text: text, spec, assumptions, status: "active" }),
    });
  } catch (error) {
    return error instanceof ApiError ? error.message : "Something went wrong.";
  }
  revalidatePath("/rules");
  return null;
}

export async function setStatus(ruleId: string, status: "active" | "paused"): Promise<void> {
  await api(`/rules/${ruleId}`, { method: "PATCH", body: JSON.stringify({ status }) });
  revalidatePath("/rules");
}
