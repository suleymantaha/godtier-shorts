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
    animationType: 'default',
    busy: false,
    currentJob: null,
    currentJobId: null,
    cutAsShort: true,
    duration: 75,
    endTime: 60,
    errorMessage: null,
    fileInputRef: { current: null },
    generatedClips: [] as Array<{ clipName: string; projectId?: string; uiTitle?: string }>,
    handleFileSelect: vi.fn(),
    handleOpenLibrary: vi.fn(),
    handleRender: vi.fn(),
    handleVideoLoadedMetadata: vi.fn(),
    isPlaying: false,
    jumpToEnd: vi.fn(),
    jumpToStart: vi.fn(),
    kesFeedback: null,
    layout: 'auto',
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
    setLayout: vi.fn(),
    setAnimationType: vi.fn(),
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

  it('passes editor state into the subtitle preview shell', () => {
    render(<AutoCutEditor />);

    expect(screen.getByLabelText('subtitle-preview-stage')).toHaveAttribute('data-shell-type', 'phone');
    expect(screen.getByTestId('subtitle-preview-media')).toHaveAttribute('src', 'blob:auto-cut');
  });

  it('mirrors split layout selection into the preview safe area', () => {
    controllerState.value = createController({ layout: 'split' });

    render(<AutoCutEditor />);

    const previewBandWrapper = screen.getByTestId('subtitle-preview-band').parentElement as HTMLElement;
    expect(previewBandWrapper.style.top).toBe('45%');
    expect(previewBandWrapper.style.bottom).toBe('');
  });

  it('shows generated clips summary and forwards the library CTA', () => {
    controllerState.value = createController({
      currentJob: {
        job_id: 'manualcut_1',
        url: '/source.mp4',
        style: 'HORMOZI',
        status: 'completed',
        progress: 100,
        last_message: 'Tamamlandi',
        created_at: 1,
        num_clips: 2,
      },
      generatedClips: [
        { clipName: 'clip-1.mp4', projectId: 'proj-1', uiTitle: 'Hook 1' },
        { clipName: 'clip-2.mp4', projectId: 'proj-1', uiTitle: 'Hook 2' },
      ],
      resultVideoSrc: '/api/projects/proj-1/shorts/clip-1.mp4',
    });

    render(<AutoCutEditor onOpenLibrary={controllerState.value?.handleOpenLibrary as () => void} />);

    expect(screen.getByText(/2 klip uretildi/i)).toBeInTheDocument();
    expect(screen.getByText('clip-1.mp4')).toBeInTheDocument();
    expect(screen.getByText('clip-2.mp4')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /clip library/i }));
    expect(controllerState.value?.handleOpenLibrary).toHaveBeenCalledTimes(1);
  });
});
