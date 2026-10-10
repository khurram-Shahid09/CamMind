export default function AuthLayout({ children }: LayoutProps<"/">) {
  return (
    <main className="flex flex-1 items-center justify-center bg-canvas px-4 py-16">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <div className="font-mono text-sm tracking-widest text-accent">CAMMIND</div>
          <p className="mt-1 text-sm text-muted">Tell your cameras what to watch for.</p>
        </div>
        <div className="rounded-xl border border-line bg-surface p-6 shadow-sm">{children}</div>
      </div>
    </main>
  );
}
