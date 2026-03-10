import { useCallback, useEffect, useRef } from 'react';

export function useThrottledCallback<Args extends unknown[]>(
  fn: (...args: Args) => void,
  delay: number,
): (...args: Args) => void {
  const lastCall = useRef(0);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const latestArgs = useRef<Args | null>(null);
  const fnRef = useRef(fn);

  useEffect(() => {
    fnRef.current = fn;
  });

  return useCallback((...args: Args) => {
    const now = Date.now();
    const remaining = delay - (now - lastCall.current);
    latestArgs.current = args;

    if (remaining <= 0) {
      if (timer.current) {
        clearTimeout(timer.current);
        timer.current = null;
      }
      lastCall.current = now;
      latestArgs.current = null;
      fnRef.current(...args);
    } else if (!timer.current) {
      timer.current = setTimeout(() => {
        lastCall.current = Date.now();
        timer.current = null;
        if (latestArgs.current) {
          fnRef.current(...latestArgs.current);
          latestArgs.current = null;
        }
      }, remaining);
    }
  }, [delay]);
}
