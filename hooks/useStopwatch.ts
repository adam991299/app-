import { useEffect, useRef, useState } from 'react';

/** Counts up in seconds from the moment it mounts — used for the puzzle timer, which
 * (per design) counts up rather than down: it's purely informational, never a pressure
 * mechanic. */
export function useStopwatch(running = true): number {
  const [elapsed, setElapsed] = useState(0);
  const startRef = useRef(Date.now());

  useEffect(() => {
    if (!running) return;
    const interval = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startRef.current) / 1000));
    }, 1000);
    return () => clearInterval(interval);
  }, [running]);

  return elapsed;
}

export function formatStopwatch(totalSeconds: number): string {
  const m = Math.floor(totalSeconds / 60);
  const s = totalSeconds % 60;
  return `${m}:${String(s).padStart(2, '0')}`;
}
