import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';

let mockClipsResponse: {
  clips: Array<{
    created_at: number;
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
const mockDeleteClip = vi.fn();
const mockListClips = vi.fn();
const authRuntimeState = {
  canUseProtectedRequests: true,
};

async function chooseSelectOption(user: ReturnType<typeof userEvent.setup>, label: RegExp, option: RegExp) {
  await user.click(screen.getByLabelText(label));
  await user.click(screen.getByRole('option', { name: option }));
}

vi.mock('../../api/client', () => ({
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

describe('ClipGallery', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    authRuntimeState.canUseProtectedRequests = true;
    mockClipsResponse = { clips: [] };
    mockShouldReject = false;
    mockDeleteClip.mockReset();
    mockDeleteClip.mockResolvedValue({
      clip_name: 'clip-1.mp4',
      deleted: true,
      project_id: 'project-1',
      status: 'deleted',
    });
    mockListClips.mockReset();
  });

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
        url: '/clips/clip-1.mp4',
        has_transcript: true,
        ui_title: 'Hot Take',
        created_at: 123,
      }],
      has_more: true,
      total: 250,
    };

    const { ClipGallery } = await import('../../components/ClipGallery');
    render(<ClipGallery />);

    expect(await screen.findByText('clip-1.mp4')).toBeInTheDocument();
    expect(screen.getByText(/clip library/i)).toBeInTheDocument();
    expect(screen.getByText(/250 clips/i)).toBeInTheDocument();
    expect(screen.getByText(/showing newest 200 clips/i)).toBeInTheDocument();
    expect(screen.getByTestId('lazy-video')).toHaveAttribute(
      'data-src',
      'http://localhost:8000/clips/clip-1.mp4?t=123',
    );
    expect(mockListClips).toHaveBeenCalledWith(1, 200);
  });

  it('shows empty state when no clips', async () => {
    const { ClipGallery } = await import('../../components/ClipGallery');
    render(<ClipGallery />);
    const empty = await screen.findByText(/no clips generated yet/i);
    expect(empty).toBeInTheDocument();
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

  it('does not start clip polling before protected auth is ready', async () => {
    authRuntimeState.canUseProtectedRequests = false;
    const { ClipGallery } = await import('../../components/ClipGallery');

    render(<ClipGallery />);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(35_000);
    });

    expect(mockListClips).not.toHaveBeenCalled();
  });

  it('renders ready clips, supports sort/filter, and forwards edit actions', async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
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

    expect(await screen.findByText('clip-1.mp4')).toBeInTheDocument();
    expect(screen.getAllByText(/clip-[12]\.mp4/i).map((element) => element.textContent)).toEqual([
      'clip-2.mp4',
      'clip-1.mp4',
    ]);

    await chooseSelectOption(user, /sort clips/i, /oldest/i);
    expect(screen.getAllByText(/clip-[12]\.mp4/i).map((element) => element.textContent)).toEqual([
      'clip-1.mp4',
      'clip-2.mp4',
    ]);

    await chooseSelectOption(user, /project filter/i, /project-1/i);
    expect(screen.getByText('clip-1.mp4')).toBeInTheDocument();
    expect(screen.queryByText('clip-2.mp4')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /subtitle edit/i }));
    expect(onEditClip).toHaveBeenCalledWith(expect.objectContaining({ name: 'clip-1.mp4' }));
    expect(screen.queryByRole('button', { name: /advanced edit/i })).not.toBeInTheDocument();
  });

  it('confirms delete and removes the clip card after success', async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
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

    expect(await screen.findByText('clip-1.mp4')).toBeInTheDocument();
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
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
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

    expect(await screen.findByText('clip-1.mp4')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /^delete$/i }));
    await user.click(screen.getByRole('button', { name: /delete clip/i }));

    expect(await screen.findByText(/delete failed/i)).toBeInTheDocument();
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getAllByText('clip-1.mp4')).toHaveLength(2);
  });
});
