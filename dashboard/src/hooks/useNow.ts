import { useEffect, useState } from "react";

/** Shared clock so staleness is evaluated against wall time, not render time. */
export function useNow(intervalMs: number): number {
  const [nowMs, setNowMs] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNowMs(Date.now()), intervalMs);
    return () => {
      clearInterval(id);
    };
  }, [intervalMs]);
  return nowMs;
}
