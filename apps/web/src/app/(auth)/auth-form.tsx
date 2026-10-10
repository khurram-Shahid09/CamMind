"use client";

import { useActionState } from "react";

import { login, type AuthState } from "./actions";

const field =
  "w-full rounded-md border border-line bg-canvas px-3 py-2 text-sm outline-none focus:border-accent focus:ring-2 focus:ring-accent/20";

export function AuthForm({ next }: { next?: string }) {
  const [state, action, pending] = useActionState<AuthState, FormData>(login, { error: null, email: "" });
  return (
    <form action={action} className="space-y-4">
      <label className="block space-y-1.5">
        <span className="text-sm font-medium">Email</span>
        <input name="email" type="email" required autoComplete="email" defaultValue={state.email} className={field} />
      </label>
      <label className="block space-y-1.5">
        <span className="text-sm font-medium">Password</span>
        <input name="password" type="password" required autoComplete="current-password" className={field} />
      </label>
      {next && <input type="hidden" name="next" value={next} />}
      {state.error && (
        <p role="alert" className="rounded-md bg-danger/10 px-3 py-2 text-sm text-danger">
          {state.error}
        </p>
      )}
      <button
        disabled={pending}
        className="w-full rounded-md bg-accent px-3 py-2 text-sm font-semibold text-canvas hover:bg-accent/90 disabled:opacity-60"
      >
        {pending ? "Please wait…" : "Sign in"}
      </button>
    </form>
  );
}
