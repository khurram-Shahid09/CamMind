const EXAMPLES = [
  "Alert me if anyone is near the back door after 10 PM",
  "Tell the principal if more than 15 students are in the parking lot during class hours",
  "Flag any worker in the press area without a helmet",
];

export default function Home() {
  return (
    <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col justify-center gap-8 px-6 py-16">
      <div className="flex flex-col gap-3">
        <p className="font-mono text-sm tracking-widest text-accent">CAMMIND</p>
        <h1 className="text-4xl font-semibold tracking-tight">
          Tell your cameras what to watch for, in plain English.
        </h1>
        <p className="text-muted">
          Write a rule, confirm what CamMind understood, and get an alert with a snapshot and a clip when it
          happens. Video stays on your own machine.
        </p>
      </div>
      <ul className="flex flex-col gap-2">
        {EXAMPLES.map((example) => (
          <li key={example} className="rounded-lg border border-line bg-surface px-4 py-3 text-sm">
            “{example}”
          </li>
        ))}
      </ul>
      <p className="text-sm text-muted">The dashboard is being built. Live view, zones and rules come next.</p>
    </main>
  );
}
