"use client";

import { useState, useTransition } from "react";

import type { Compiled, Site } from "@/lib/types";

import { activateRule, compileRule } from "./actions";

const EXAMPLES = [
  "Alert me if anyone is near the back door after 10 PM",
  "Tell security if anyone enters the campus through the gate",
  "Flag any worker in the press area without a helmet",
  "Tell me when my brother Ali comes home",
];

export function NewRule({ sites }: { sites: Site[] }) {
  const [text, setText] = useState("");
  const [siteId, setSiteId] = useState(sites[0]?.id ?? "");
  const [result, setResult] = useState<Compiled | null>(null);
  const [showJson, setShowJson] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [pending, start] = useTransition();

  const compile = () =>
    start(async () => {
      setMessage(null);
      setResult(await compileRule(text, siteId));
    });
  const activate = () =>
    start(async () => {
      if (!result?.spec) return;
      const name = text.length > 60 ? `${text.slice(0, 57)}…` : text;
      const error = await activateRule(siteId, name, text, result.spec, result.assumptions ?? []);
      if (error) setMessage(error);
      else {
        setMessage("Rule activated. The worker picks it up within 30 seconds.");
        setResult(null);
        setText("");
      }
    });

  return (
    <section className="space-y-4 rounded-xl border border-line bg-surface p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-semibold">New rule, in plain English</h2>
        <select
          value={siteId}
          onChange={(e) => setSiteId(e.target.value)}
          className="rounded-md border border-line bg-canvas px-2 py-1 text-sm"
          aria-label="Site"
        >
          {sites.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
      </div>
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={2}
        placeholder="e.g. Alert me if anyone is near the back door after 10 PM"
        className="w-full resize-none rounded-lg border border-line bg-canvas px-3 py-2 text-lg outline-none focus:border-accent"
      />
      <div className="flex flex-wrap gap-2">
        {EXAMPLES.map((example) => (
          <button
            key={example}
            type="button"
            onClick={() => setText(example)}
            className="rounded-full border border-line px-3 py-1 text-xs text-muted hover:border-accent hover:text-ink"
          >
            {example}
          </button>
        ))}
      </div>
      <button
        onClick={compile}
        disabled={pending || !text.trim()}
        className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-canvas disabled:opacity-50"
      >
        {pending && !result ? "Understanding…" : "Understand this rule"}
      </button>

      {result && (
        <div className="space-y-3 rounded-lg border border-line bg-canvas p-4" data-testid="compiled">
          {result.kind === "rule" && (
            <>
              <p className="text-xs uppercase tracking-wider text-muted">What CamMind understood</p>
              <p className="text-lg font-medium leading-snug">{result.summary}</p>
              {!!result.assumptions?.length && (
                <ul className="space-y-1 text-sm text-muted">
                  {result.assumptions.map((a) => (
                    <li key={a}>ℹ {a}</li>
                  ))}
                </ul>
              )}
              <div className="flex flex-wrap gap-2 pt-1">
                <button
                  onClick={activate}
                  disabled={pending}
                  className="rounded-md bg-ok px-4 py-2 text-sm font-semibold text-canvas disabled:opacity-50"
                >
                  Activate
                </button>
                <button onClick={() => setShowJson(!showJson)} className="rounded-md border border-line px-3 py-2 text-sm">
                  {showJson ? "Hide" : "Show"} JSON
                </button>
              </div>
              {showJson && (
                <pre className="max-h-72 overflow-auto rounded-md bg-surface p-3 font-mono text-xs">
                  {JSON.stringify(result.spec, null, 2)}
                </pre>
              )}
            </>
          )}
          {result.kind === "question" && (
            <p>
              <span className="font-medium">CamMind needs to know: </span>
              {result.question}
            </p>
          )}
          {result.kind === "unsupported" && (
            <div className="space-y-1">
              <p className="font-medium text-warn">Can&apos;t do this: {result.reason}</p>
              {result.suggestion && <p className="text-sm text-muted">Try instead: “{result.suggestion}”</p>}
            </div>
          )}
          {(result.kind === "invalid" || result.kind === "error") && (
            <p className="text-danger">{result.errors?.join("; ")}</p>
          )}
        </div>
      )}
      {message && <p className="text-sm text-ok">{message}</p>}
    </section>
  );
}
