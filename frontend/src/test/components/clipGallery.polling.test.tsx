import { act, renderHook } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';

import { useAuthRuntimeStore } from '../../auth/runtime';
import { useJobStore } from '../../store/useJobStore';
import { useClipGalleryController } from '../../components/clipGallery/useClipGalleryController';

const list = vi.hoisted(() => vi.fn());
vi.mock('../../api/client', () => ({ clipsApi: { list } }));

afterEach(() => { vi.useRealTimers(); });

it('polls only on the interval when every response contains a fresh clips array', async () => {
  vi.useFakeTimers();
  useJobStore.getState().reset();
  useAuthRuntimeStore.setState({ canUseProtectedRequests: true, pauseReason: null });
  list.mockReset().mockImplementation(async () => ({ clips: [], total: 0 }));
  const hook = renderHook(() => useClipGalleryController());
  await act(async () => { await vi.advanceTimersByTimeAsync(250); });
  expect(list).toHaveBeenCalledTimes(1);
  hook.rerender();
  await act(async () => { await vi.advanceTimersByTimeAsync(9000); });
  expect(list).toHaveBeenCalledTimes(1);
  await act(async () => { await vi.advanceTimersByTimeAsync(1000); });
  expect(list).toHaveBeenCalledTimes(2);
  hook.unmount();
  await act(async () => { await vi.advanceTimersByTimeAsync(10000); });
  expect(list).toHaveBeenCalledTimes(2);
});
