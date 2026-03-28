import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useJobStore } from '../../store/useJobStore';

let mockClipsResponse: {
  clips: Array<{
    created_at: number;
    duration?: number | null;
    has_transcript: boolean;
    name: string;
    project?: string;
    ui_title?: string;
    url: string;
  }>;
  has_more?: boolean;
  total?: number;
};
let mockShouldReject: boolean;
let mockOwnershipDiagnosticsError: Error | null;
let mockOwnershipDiagnosticsResponse: {
  auth_mode: 'clerk_jwt' | 'static_token';
  current_subject: string;
  current_subject_hash: string;
  reclaimable_projects: Array<{
    clip_count: number;
    created_at: string;
    latest_clip_name?: string | null;
    owner_subject_hash: string;
    project_id: string;
    source: string;
    status: string;
  }>;
  token_type: 'jwt' | 'bearer';
  visible_project_count: number;
};
const mockClaimProjectOwnership = vi.fn();
const mockOwnershipDiagnostics = vi.fn();
const mockDeleteClip = vi.fn();
const mockListClips = vi.fn();
const windowOpenMock = vi.fn();
const authRuntimeState = {
  backendIdentity: {
    authMode: 'clerk_jwt' as 'clerk_jwt' | 'static_token',
    subject: 'clerk-user-1',
    subjectHash: 'a4069ffa93794396e1a7bf578c6a7b8b',
    tokenType: 'jwt' as 'jwt' | 'bearer',
  },
  canUseProtectedRequests: true,
  pauseReason: null as string | null,
};

async function chooseSelectOption(user: ReturnType<typeof userEvent.setup>, label: RegExp, option: RegExp) {
  await user.click(screen.getByLabelText(label));
  await user.click(screen.getByRole('option', { name: option }));
}

vi.mock('../../api/client', () => ({
  authApi: {
    claimProjectOwnership: (...args: unknown[]) => mockClaimProjectOwnership(...args),
    ownershipDiagnostics: (...args: unknown[]) => {
      mockOwnershipDiagnostics(...args);
      if (mockOwnershipDiagnosticsError) return Promise.reject(mockOwnershipDiagnosticsError);
      return Promise.resolve(mockOwnershipDiagnosticsResponse);
    },
  },
  clipsApi: {
    delete: (...args: unknown[]) => mockDeleteClip(...args),
    list: (...args: unknown[]) => {
      mockListClips(...args);
      if (mockShouldReject) return Promise.reject(new Error('Network error'));
      return Promise.resolve(mockClipsResponse);
    },
  },
  socialApi: {
    getAccounts: () => Promise.resolve({ connected: false, provider: 'postiz', accounts: [] }),
    getPrefill: () => Promise.resolve({
      project_id: 'p',
      clip_name: 'c.mp4',
      clip_exists: true,
      source: { has_clip_metadata: false, has_drafts: false, viral_metadata: null },
      platforms: {
        youtube_shorts: { title: '', text: '', hashtags: [] },
        tiktok: { title: '', text: '', hashtags: [] },
        instagram_reels: { title: '', text: '', hashtags: [] },
        facebook_reels: { title: '', text: '', hashtags: [] },
        x: { title: '', text: '', hashtags: [] },
        linkedin: { title: '', text: '', hashtags: [] },
      },
    }),
    getPublishJobs: () => Promise.resolve({ jobs: [] }),
    publish: () => Promise.resolve({ status: 'queued', jobs: [] }),
    saveDrafts: () => Promise.resolve({ status: 'saved' }),
    saveCredentials: () => Promise.resolve({ status: 'connected', provider: 'postiz', accounts: [] }),
    deleteCredentials: () => Promise.resolve({ status: 'deleted', provider: 'postiz' }),
    approveJob: () => Promise.resolve({ status: 'approved', job_id: 'x' }),
    cancelJob: () => Promise.resolve({ status: 'cancelled', job_id: 'x' }),
  },
}));

vi.mock('../../auth/runtime', () => ({
  useAuthRuntimeStore: (selector: (state: typeof authRuntimeState) => unknown) => selector(authRuntimeState),
}));

vi.mock('../../config', () => ({
  API_BASE: 'http://localhost:8000',
}));

vi.mock('../../components/ui/LazyVideo', () => ({
  LazyVideo: ({ src, className }: { src: string; className?: string }) => (
    <div data-testid="lazy-video" data-src={src} className={className} />
  ),
}));

beforeEach(() => {
  vi.useRealTimers();
  windowOpenMock.mockReset();
  Object.defineProperty(window, 'open', { configurable: true, value: windowOpenMock });
  useJobStore.getState().reset();
  authRuntimeState.canUseProtectedRequests = true;
  authRuntimeState.backendIdentity = {
    authMode: 'clerk_jwt',
    subject: 'clerk-user-1',
    subjectHash: 'a4069ffa93794396e1a7bf578c6a7b8b',
    tokenType: 'jwt',
  };
  authRuntimeState.pauseReason = null;
  mockOwnershipDiagnosticsError = null;
  mockClipsResponse = { clips: [] };
  mockOwnershipDiagnosticsResponse = {
    auth_mode: 'clerk_jwt',
    current_subject: 'clerk-user-1',
    current_subject_hash: 'a4069ffa93794396e1a7bf578c6a7b8b',
    reclaimable_projects: [],
    token_type: 'jwt',
    visible_project_count: 0,
  };
  mockShouldReject = false;
  mockClaimProjectOwnership.mockReset();
  mockClaimProjectOwnership.mockResolvedValue({
    status: 'claimed',
    clip_count: 1,
    current_subject_hash: 'a4069ffa93794396e1a7bf578c6a7b8b',
    metadata_files_updated: 1,
    new_project_id: 'project-claimed',
    old_project_id: 'project-legacy',
  });
  mockDeleteClip.mockReset();
  mockDeleteClip.mockResolvedValue({
    clip_name: 'clip-1.mp4',
    deleted: true,
    project_id: 'project-1',
    status: 'deleted',
  });
  mockListClips.mockReset();
  mockOwnershipDiagnostics.mockReset();
});

afterEach(() => {
  vi.useRealTimers();
});

describe('ClipGallery loading and empty states', () => {
  it('shows loading state initially', async () => {
    const { ClipGallery } = await import('../../components/ClipGallery');
    render(<ClipGallery />);
    expect(screen.getByText(/indexing clip library|yukleniyor/i)).toBeInTheDocument();
  });

  it('loads the clip library with total count and page size 200', async () => {
    mockClipsResponse = {
      clips: [{
        name: 'clip-1.mp4',
        project: 'project-1',
        resolved_project_id: 'project-1',
        transcript_status: 'ready',
        url: '/clips/clip-1.mp4',
        has_transcript: true,
        ui_title: 'Hot Take',
        created_at: 123,
        duration: 75,
      }],
      has_more: true,
      total: 250,
    };

    const { ClipGallery } = await import('../../components/ClipGallery');
    render(<ClipGallery />);

    expect((await screen.findAllByText('clip-1.mp4')).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/clip library/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/250 clips/i)).toBeInTheDocument();
    expect(screen.getByText(/showing newest 200 clips/i)).toBeInTheDocument();
    expect(screen.getByText(/only owner-scoped new outputs are indexed/i)).toBeInTheDocument();
    expect(screen.getByText(/account a4069ffa\.\.\.7b8b \| clerk/i)).toBeInTheDocument();
    expect(screen.getAllByText('1:15').length).toBeGreaterThan(0);
    expect(screen.getByTestId('lazy-video')).toHaveAttribute(
      'data-src',
      'http://localhost:8000/clips/clip-1.mp4?t=123',
    );
    expect(mockListClips).toHaveBeenCalledWith(1, 200);
  });

  it('opens the social workspace tab when sharing a clip', async () => {
    mockClipsResponse = {
      clips: [{
        name: 'clip-share.mp4',
        project: 'project-1',
        resolved_project_id: 'project-1',
        transcript_status: 'ready',
        url: '/clips/clip-share.mp4',
        has_transcript: true,
        ui_title: 'Share Me',
        created_at: 456,
        duration: 42,
      }],
      total: 1,
    };

    const { ClipGallery } = await import('../../components/ClipGallery');
    render(<ClipGallery />);

    expect(await screen.findByText('clip-share.mp4')).toBeInTheDocument();
    const shareButtons = screen.getAllByRole('button', { name: /share/i, hidden: true });
    fireEvent.click(shareButtons[shareButtons.length - 1]);

    await waitFor(() => {
      expect(windowOpenMock).toHaveBeenCalledWith(
        expect.stringContaining('/social-compose'),
        '_self',
      );
      expect(windowOpenMock).toHaveBeenCalledWith(
        expect.stringContaining('clip_name=clip-share.mp4'),
        '_self',
      );
      expect(windowOpenMock).toHaveBeenCalledWith(
        expect.stringContaining('project_id=project-1'),
        '_self',
      );
    });
  });

  it('renders transcript processing and recovery-needed badges from transcript_status', async () => {
    mockClipsResponse = {
      clips: [
        {
          name: 'clip-processing.mp4',
          project: 'project-1',
          resolved_project_id: 'project-1',
          transcript_status: 'project_pending',
          url: '/clips/clip-processing.mp4',
          has_transcript: false,
          created_at: 123,
        },
        {
          name: 'clip-recovery.mp4',
          project: 'project-1',
          resolved_project_id: 'project-1',
          transcript_status: 'needs_recovery',
          url: '/clips/clip-recovery.mp4',
          has_transcript: false,
          created_at: 122,
        },
      ],
      total: 2,
    };

    const { ClipGallery } = await import('../../components/ClipGallery');
    render(<ClipGallery />);

    expect((await screen.findAllByText('clip-processing.mp4')).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/transcript processing/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/transcript recovery needed/i).length).toBeGreaterThan(0);
  });

  it('falls back to the last verified backend identity when ownership diagnostics are unavailable', async () => {
    mockOwnershipDiagnosticsError = new Error('ownership unavailable');
    mockClipsResponse = {
      clips: [{
        name: 'clip-1.mp4',
        project: 'project-1',
        url: '/clips/clip-1.mp4',
        has_transcript: true,
        created_at: 123,
      }],
      total: 1,
    };

    const { ClipGallery } = await import('../../components/ClipGallery');
    render(<ClipGallery />);

    expect((await screen.findAllByText('clip-1.mp4')).length).toBeGreaterThan(0);
    expect(screen.getByText(/account a4069ffa\.\.\.7b8b \| clerk/i)).toBeInTheDocument();
    expect(screen.queryByText(/account unknown/i)).not.toBeInTheDocument();
  });

  it('shows empty state when no clips', async () => {
    const { ClipGallery } = await import('../../components/ClipGallery');
    render(<ClipGallery />);
    const empty = await screen.findByText(/no clips generated yet/i);
    expect(empty).toBeInTheDocument();
    expect(screen.getByText(/clip library only lists generated shorts clips/i)).toBeInTheDocument();
  });

  it('shows processing state before the first clip when a clip-producing job is active', async () => {
    useJobStore.setState({
      jobs: [{
        job_id: 'manualcut_123',
        url: '/source.mp4',
        style: 'HORMOZI',
        status: 'processing',
        progress: 15,
        last_message: 'Processing',
        created_at: 1,
      }],
    });

    const { ClipGallery } = await import('../../components/ClipGallery');
    render(<ClipGallery />);

    expect(await screen.findByText(/rendering clips/i)).toBeInTheDocument();
    expect(screen.getByText(/the first ready clip will appear here as soon as rendering completes/i)).toBeInTheDocument();
  });

  it('shows error state with retry button on fetch failure', async () => {
    mockShouldReject = true;
    const { ClipGallery } = await import('../../components/ClipGallery');
    render(<ClipGallery />);

    const errorEl = await screen.findByRole('alert');
    expect(errorEl).toBeInTheDocument();

    const retryBtn = screen.getByRole('button', { name: /tekrar|retry/i });
    expect(retryBtn).toBeInTheDocument();
  });
});

describe('ClipGallery auth and refresh behavior', () => {
  it('tries a recovery fetch when protected auth bootstrap stays in loading without a pause reason', async () => {
    vi.useFakeTimers();
    authRuntimeState.canUseProtectedRequests = false;
    authRuntimeState.pauseReason = null;
    mockClipsResponse = {
      clips: [{
        name: 'clip-bootstrap.mp4',
        project: 'project-1',
        url: '/clips/clip-bootstrap.mp4',
        has_transcript: true,
        created_at: 111,
      }],
      total: 1,
    };
    const { ClipGallery } = await import('../../components/ClipGallery');

    render(<ClipGallery />);

    expect(screen.getByText(/indexing clip library|yukleniyor/i)).toBeInTheDocument();
    expect(screen.queryByText(/clip library beklemede/i)).not.toBeInTheDocument();
    expect(mockListClips).not.toHaveBeenCalled();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2600);
    });

    expect(mockListClips).toHaveBeenCalledTimes(1);
  });

  it('shows an auth-blocked state before protected auth is ready', async () => {
    vi.useFakeTimers();
    authRuntimeState.canUseProtectedRequests = false;
    authRuntimeState.pauseReason = 'unauthorized';
    const { ClipGallery } = await import('../../components/ClipGallery');

    render(<ClipGallery />);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(35_000);
    });

    expect(screen.getByText(/transcript access pending/i)).toBeInTheDocument();
    expect(mockListClips).not.toHaveBeenCalled();
  });

  it('tries a forced recovery fetch when retry is clicked in auth-blocked state', async () => {
    const user = userEvent.setup();
    authRuntimeState.canUseProtectedRequests = false;
    authRuntimeState.pauseReason = 'unauthorized';
    mockClipsResponse = {
      clips: [{
        name: 'clip-recovered.mp4',
        project: 'project-1',
        url: '/clips/clip-recovered.mp4',
        has_transcript: true,
        created_at: 999,
      }],
      total: 1,
    };

    const { ClipGallery } = await import('../../components/ClipGallery');
    render(<ClipGallery />);

    const retryBtn = await screen.findByRole('button', { name: /retry clip library|retry/i });
    await user.click(retryBtn);

    await waitFor(() => expect(mockListClips).toHaveBeenCalledTimes(1));
  });

  it('refetches clips when clip-ready signal arrives and reveals the first clip', async () => {
    useJobStore.setState({
      jobs: [{
        job_id: 'manual_123',
        url: '/source.mp4',
        style: 'HORMOZI',
        status: 'processing',
        progress: 25,
        last_message: 'Processing',
        created_at: 1,
      }],
    });

    const { ClipGallery } = await import('../../components/ClipGallery');
    render(<ClipGallery />);

    expect(await screen.findByText(/rendering clips/i)).toBeInTheDocument();

    mockClipsResponse = {
      clips: [{
        name: 'clip-ready.mp4',
        project: 'project-1',
        url: '/clips/clip-ready.mp4',
        has_transcript: true,
        ui_title: 'Hook',
        created_at: 456,
      }],
      total: 1,
    };

    act(() => {
      useJobStore.getState().markClipReady({
        at: '2026-03-20T00:00:01.000Z',
        clipName: 'clip-ready.mp4',
        job_id: 'manual_123',
        message: 'Klip hazir',
        progress: 90,
        projectId: 'project-1',
        uiTitle: 'Hook',
      });
    });

    expect((await screen.findAllByText('clip-ready.mp4')).length).toBeGreaterThan(0);
  });
});

describe('ClipGallery stale refresh handling', () => {
  it('shows a stale refresh warning when a later clip refresh fails after initial load', async () => {
    mockClipsResponse = {
      clips: [{
        name: 'clip-1.mp4',
        project: 'project-1',
        url: '/clips/clip-1.mp4',
        has_transcript: true,
        ui_title: 'Hot Take',
        created_at: 123,
      }],
      total: 1,
    };

    const { ClipGallery } = await import('../../components/ClipGallery');
    render(<ClipGallery />);
    expect((await screen.findAllByText('clip-1.mp4')).length).toBeGreaterThan(0);

    mockShouldReject = true;

    act(() => {
      useJobStore.getState().markClipReady({
        at: '2026-03-20T00:00:03.000Z',
        clipName: 'clip-2.mp4',
        job_id: 'manual_123',
        message: 'Klip hazir',
        progress: 95,
        projectId: 'project-1',
        uiTitle: 'Second',
      });
    });

    expect(await screen.findByText(/library refresh failed/i)).toBeInTheDocument();
    expect(screen.getAllByText('clip-1.mp4').length).toBeGreaterThan(0);
  });
});

describe('ClipGallery interactions - browse and edit', () => {
  it('renders ready clips, supports sort/filter, and forwards edit actions', async () => {
    const user = userEvent.setup();
    const onEditClip = vi.fn();
    mockClipsResponse = {
      clips: [
        {
          name: 'clip-1.mp4',
          project: 'project-1',
          url: '/clips/clip-1.mp4',
          has_transcript: true,
          ui_title: 'Alpha',
          created_at: 100,
        },
        {
          name: 'clip-2.mp4',
          project: 'project-2',
          url: '/clips/clip-2.mp4',
          has_transcript: false,
          ui_title: 'Beta',
          created_at: 200,
        },
      ],
      total: 2,
    };

    const { ClipGallery } = await import('../../components/ClipGallery');
    render(<ClipGallery onEditClip={onEditClip} />);

    expect((await screen.findAllByText('clip-1.mp4')).length).toBeGreaterThan(0);
    expect(screen.getAllByRole('button', { name: /show details for clip-[12]\.mp4/i }).map((element) => element.getAttribute('aria-label'))).toEqual([
      'Show details for clip-2.mp4',
      'Show details for clip-1.mp4',
    ]);

    await chooseSelectOption(user, /sort clips/i, /oldest/i);
    expect(screen.getAllByRole('button', { name: /show details for clip-[12]\.mp4/i }).map((element) => element.getAttribute('aria-label'))).toEqual([
      'Show details for clip-1.mp4',
      'Show details for clip-2.mp4',
    ]);

    await chooseSelectOption(user, /project filter/i, /project-1/i);
    expect(screen.getAllByText('clip-1.mp4').length).toBeGreaterThan(0);
    expect(screen.queryAllByText('clip-2.mp4')).toHaveLength(0);

    await user.click(screen.getByRole('button', { name: /show details for clip-1\.mp4/i }));
    await user.click(screen.getByRole('button', { name: /subtitle edit/i }));
    expect(onEditClip).toHaveBeenCalledWith(expect.objectContaining({ name: 'clip-1.mp4' }));
    expect(screen.queryByRole('button', { name: /advanced edit/i })).not.toBeInTheDocument();
  });

  it('shows reclaimable projects and claims them into the current account', async () => {
    const user = userEvent.setup();
    mockOwnershipDiagnosticsResponse = {
      auth_mode: 'clerk_jwt',
      current_subject: 'clerk-user-1',
      current_subject_hash: 'a4069ffa93794396e1a7bf578c6a7b8b',
      reclaimable_projects: [{
        clip_count: 1,
        created_at: '2026-03-21T12:00:18.810686+00:00',
        latest_clip_name: 'clip.mp4',
        owner_subject_hash: '28ea82a4a3257f9fa00a1c8f083faa38',
        project_id: 'project-legacy',
        source: 'youtube',
        status: 'active',
      }],
      token_type: 'jwt',
      visible_project_count: 0,
    };

    const { ClipGallery } = await import('../../components/ClipGallery');
    render(<ClipGallery />);

    expect(await screen.findByText(/claim it to account a4069ffa\.\.\.7b8b/i)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /claim project/i }));

    await waitFor(() => expect(mockClaimProjectOwnership).toHaveBeenCalledWith('project-legacy'));
  });
});

describe('ClipGallery interactions - delete flows', () => {
  it('confirms delete and removes the clip card after success', async () => {
    const user = userEvent.setup();
    mockClipsResponse = {
      clips: [{
        name: 'clip-1.mp4',
        project: 'project-1',
        url: '/clips/clip-1.mp4',
        has_transcript: true,
        ui_title: 'Hot Take',
        created_at: 123,
      }],
      total: 1,
    };
    mockDeleteClip.mockImplementation(async () => {
      mockClipsResponse = { clips: [], total: 0 };
      return {
        clip_name: 'clip-1.mp4',
        deleted: true,
        project_id: 'project-1',
        status: 'deleted',
      };
    });

    const { ClipGallery } = await import('../../components/ClipGallery');
    render(<ClipGallery />);

    expect((await screen.findAllByText('clip-1.mp4')).length).toBeGreaterThan(0);
    await user.click(screen.getByRole('button', { name: /show details for clip-1\.mp4/i }));
    await user.click(screen.getByRole('button', { name: /^delete$/i }));
    expect(screen.getByRole('dialog')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /delete clip/i }));

    await waitFor(() => {
      expect(mockDeleteClip).toHaveBeenCalledWith('project-1', 'clip-1.mp4');
    });
    await waitFor(() => {
      expect(screen.queryByText('clip-1.mp4')).not.toBeInTheDocument();
    });
  });

  it('shows inline delete error when delete request fails', async () => {
    const user = userEvent.setup();
    mockClipsResponse = {
      clips: [{
        name: 'clip-1.mp4',
        project: 'project-1',
        url: '/clips/clip-1.mp4',
        has_transcript: true,
        ui_title: 'Hot Take',
        created_at: 123,
      }],
      total: 1,
    };
    mockDeleteClip.mockRejectedValue(new Error('Delete failed'));

    const { ClipGallery } = await import('../../components/ClipGallery');
    render(<ClipGallery />);

    expect((await screen.findAllByText('clip-1.mp4')).length).toBeGreaterThan(0);
    await user.click(screen.getByRole('button', { name: /show details for clip-1\.mp4/i }));
    await user.click(screen.getByRole('button', { name: /^delete$/i }));
    await user.click(screen.getByRole('button', { name: /delete clip/i }));

    expect(await screen.findByText(/delete failed/i)).toBeInTheDocument();
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getAllByText('clip-1.mp4').length).toBeGreaterThanOrEqual(2);
  });
});
