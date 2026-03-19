import { act, renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { useAutoCutEditorActions } from '../../components/autoCutEditor/useAutoCutEditorActions';

function createParams(overrides: Partial<Parameters<typeof useAutoCutEditorActions>[0]> = {}) {
  return {
    cutAsShort: true,
    duration: 0,
    endTime: 90,
    fetchJobs: vi.fn(async () => {}),
    fileInputRef: { current: null },
    layout: 'auto',
    markers: [],
    numClips: 1,
    selectedFile: null,
    setCurrentJobId: vi.fn(),
    setDuration: vi.fn(),
    setEndTime: vi.fn(),
    setIsSubmitting: vi.fn(),
    setKesFeedback: vi.fn(),
    setLocalSrc: vi.fn(),
    setMarkers: vi.fn(),
    setNumClips: vi.fn(),
    setPendingOutputUrl: vi.fn(),
    setProjectId: vi.fn(),
    setRequestError: vi.fn(),
    setSelectedFile: vi.fn(),
    setStartTime: vi.fn(),
    skipSubtitles: false,
    startTime: 60,
    style: 'TIKTOK' as const,
    videoRef: { current: null },
    ...overrides,
  };
}

describe('useAutoCutEditorActions', () => {
  it('records loaded video duration and clamps the selected range', () => {
    const params = createParams();
    const { result } = renderHook(() => useAutoCutEditorActions(params));

    act(() => {
      result.current.handleVideoLoadedMetadata({
        currentTarget: { duration: 24 },
      } as React.SyntheticEvent<HTMLVideoElement>);
    });

    expect(params.setDuration).toHaveBeenCalledWith(24);
    expect(params.setStartTime).toHaveBeenCalledWith(23.5);
    expect(params.setEndTime).toHaveBeenCalledWith(24);
  });

  it('clears stale duration when a new file is selected', () => {
    const params = createParams();
    const { result } = renderHook(() => useAutoCutEditorActions(params));
    const file = new File(['video'], 'long-video.mp4', { type: 'video/mp4' });

    act(() => {
      result.current.handleFileSelect({
        target: { files: [file] },
      } as React.ChangeEvent<HTMLInputElement>);
    });

    expect(params.setSelectedFile).toHaveBeenCalledWith(file);
    expect(params.setCurrentJobId).toHaveBeenCalledWith(null);
    expect(params.setDuration).toHaveBeenCalledWith(0);
    expect(params.setMarkers).toHaveBeenCalledWith([]);
  });
});
