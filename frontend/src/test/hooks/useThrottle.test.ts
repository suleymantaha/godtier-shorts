import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useThrottledCallback } from '../../hooks/useThrottle';

describe('useThrottledCallback', () => {
  beforeEach(() => { vi.useFakeTimers(); });
  afterEach(() => { vi.useRealTimers(); });

  it('calls immediately on first invocation', () => {
    const spy = vi.fn();
    const { result } = renderHook(() => useThrottledCallback(spy, 200));

    act(() => { result.current(42); });
    expect(spy).toHaveBeenCalledTimes(1);
    expect(spy).toHaveBeenCalledWith(42);
  });

  it('throttles subsequent calls within delay', () => {
    const spy = vi.fn();
    const { result } = renderHook(() => useThrottledCallback(spy, 200));

    act(() => { result.current(1); });
    act(() => { result.current(2); });
    act(() => { result.current(3); });

    expect(spy).toHaveBeenCalledTimes(1);

    act(() => { vi.advanceTimersByTime(200); });
    expect(spy).toHaveBeenCalledTimes(2);
    expect(spy).toHaveBeenLastCalledWith(3);
  });

  it('allows call after delay expires', () => {
    const spy = vi.fn();
    const { result } = renderHook(() => useThrottledCallback(spy, 100));

    act(() => { result.current('a'); });
    act(() => { vi.advanceTimersByTime(100); });
    act(() => { result.current('b'); });

    expect(spy).toHaveBeenCalledTimes(2);
    expect(spy).toHaveBeenLastCalledWith('b');
  });
});
