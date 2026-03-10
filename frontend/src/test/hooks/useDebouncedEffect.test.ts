import { renderHook } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useDebouncedEffect } from '../../hooks/useDebouncedEffect';

describe('useDebouncedEffect', () => {
  beforeEach(() => { vi.useFakeTimers(); });
  afterEach(() => { vi.useRealTimers(); });

  it('fires immediately on mount', () => {
    const spy = vi.fn();
    renderHook(() => useDebouncedEffect(spy, [1], 500));
    expect(spy).toHaveBeenCalledTimes(1);
  });

  it('debounces subsequent dep changes', () => {
    const spy = vi.fn();
    const { rerender } = renderHook(
      ({ dep }) => useDebouncedEffect(spy, [dep], 300),
      { initialProps: { dep: 1 } },
    );

    expect(spy).toHaveBeenCalledTimes(1);

    rerender({ dep: 2 });
    rerender({ dep: 3 });
    expect(spy).toHaveBeenCalledTimes(1);

    vi.advanceTimersByTime(300);
    expect(spy).toHaveBeenCalledTimes(2);
  });
});
