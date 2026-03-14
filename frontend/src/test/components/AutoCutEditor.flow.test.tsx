import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { AutoCutEditor } from '../../components/AutoCutEditor';

const { controllerState } = vi.hoisted(() => ({
  controllerState: {
    value: null as Record<string, unknown> | null,
  },
}));

vi.mock('../../components/autoCutEditor/useAutoCutEditorController', () => ({
  useAutoCutEditorController: () => controllerState.value,
}));

function createController(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    addCurrentMarker: vi.fn(),
    busy: false,
    currentJob: null,
    currentJobId: null,
    cutAsShort: true,
    duration: 75,
    endTime: 60,
    errorMessage: null,
    fileInputRef: { current: null },
    handleFileSelect: vi.fn(),
    handleRender: vi.fn(),
    handleVideoLoadedMetadata: vi.fn(),
    isPlaying: false,
    jumpToEnd: vi.fn(),
    jumpToStart: vi.fn(),
    kesFeedback: null,
    markers: [] as number[],
    numClips: 1,
    openFilePicker: vi.fn(),
    processing: false,
    projectId: 'proj_1',
    queuePosition: null,
    removeMarker: vi.fn(),
    resultVideoSrc: undefined,
    selectedFile: new File(['video'], 'clip.mp4', { type: 'video/mp4' }),
    setCutAsShort: vi.fn(),
    setIsPlaying: vi.fn(),
    setSkipSubtitles: vi.fn(),
    setStyle: vi.fn(),
    skipSubtitles: false,
    startTime: 0,
    style: 'HORMOZI',
    togglePlay: vi.fn(),
    updateRange: vi.fn(),
    updateSelectedClipCount: vi.fn(),
    videoRef: { current: null },
    videoSrc: 'blob:auto-cut',
    ...overrides,
  };
}

describe('AutoCutEditor page flow', () => {
  beforeEach(() => {
    controllerState.value = createController();
  });

  it('shows the single-render CTA and forwards the click to the controller', () => {
    render(<AutoCutEditor />);

    fireEvent.click(screen.getByRole('button', { name: /otomatik cut uret/i }));

    expect(controllerState.value?.handleRender).toHaveBeenCalledTimes(1);
  });

  it('switches the CTA label when AI multi-clip mode is active', () => {
    controllerState.value = createController({ numClips: 3 });

    render(<AutoCutEditor />);

    expect(screen.getByRole('button', { name: /ai ile 3 klip uret/i })).toBeInTheDocument();
  });
});
