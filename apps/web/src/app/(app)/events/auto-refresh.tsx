"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

/** Re-renders the server page every few seconds (SSE comes later; docs/20, pending). */
export function AutoRefresh({ seconds }: { seconds: number }) {
  const router = useRouter();
  useEffect(() => {
    const timer = setInterval(() => router.refresh(), seconds * 1000);
    return () => clearInterval(timer);
  }, [router, seconds]);
  return null;
}
