import { useEffect, useRef } from 'react';

export function useDebouncedEffect(
  fn: () => void,
  deps: unknown[],
  delay: number,
): void {
  const mounted = useRef(false);

  useEffect(() => {
    if (!mounted.current) {
      mounted.current = true;
      fn();
      return;
    }

    const timer = setTimeout(fn, delay);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}
