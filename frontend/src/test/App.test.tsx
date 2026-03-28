import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import App from '../App';
import { APP_STATE_STORAGE_KEY } from '../app/helpers';
import { AUTH_IDENTITY_STORAGE_KEY, JOB_HISTORY_STORAGE_KEY } from '../auth/isolation';
import { AUTH_SNAPSHOT_STORAGE_KEY } from '../auth/session';
import type { ResilientAuthState } from '../auth/useResilientAuth';
import i18n from '../i18n';

const toggleThemeMock = vi.fn();
const useWebSocketMock = vi.fn();
const resetJobStoreMock = vi.fn();
const resilientAuthState: ResilientAuthState = {
  backendAuthStatus: 'fresh',
  canAccessApp: true,
  canUseBackend: true,
  error: null,
  identityKey: 'user-1',
  isOnline: true,
  notice: null,
  pauseReason: null,
  showUserMenu: true,
  status: 'authenticated',
  tokenExpiresAt: null,
};

vi.mock('@clerk/clerk-react', () => ({
  SignIn: () => <div>SignIn</div>,
  UserButton: () => <div>UserButton</div>,
  useUser: () => ({ user: { delete: vi.fn() } }),
}));

vi.mock('../auth/useResilientAuth', () => ({
  useResilientAuth: () => resilientAuthState,
}));

vi.mock('../hooks/useWebSocket', () => ({
  useWebSocket: (...args: unknown[]) => useWebSocketMock(...args),
}));

vi.mock('../store/useJobStore', () => ({
  useJobStore: Object.assign(
    (selector: (state: { wsStatus: string }) => unknown) => selector({ wsStatus: 'connected' }),
    { getState: () => ({ reset: resetJobStoreMock }) },
  ),
}));

vi.mock('../store/useThemeStore', () => ({
  useThemeStore: () => ({ theme: 'dark', toggleTheme: toggleThemeMock }),
}));

vi.mock('../components/JobForm', () => ({
  JobForm: ({
    onSkipSubtitlesChange,
    onStyleChange,
  }: {
    onSkipSubtitlesChange: (disabled: boolean) => void;
    onStyleChange: (styleName: string) => void;
  }) => (
    <div>
      <button onClick={() => onStyleChange('HORMOZI')}>Change Style</button>
      <button onClick={() => onSkipSubtitlesChange(true)}>Disable Subtitles</button>
    </div>
  ),
}));

vi.mock('../components/HoloTerminal', () => ({ HoloTerminal: () => <div data-testid="config-logs">HoloTerminal</div> }));
vi.mock('../components/JobQueue', () => ({ JobQueue: () => <div data-testid="job-queue">JobQueue</div> }));
vi.mock('../components/SubtitlePreview', () => ({
  SubtitlePreview: ({ disabled, size, styleName }: { disabled: boolean; size?: 'compact' | 'default' | 'tall'; styleName: string }) => (
    <div data-testid="config-preview">{`SubtitlePreview:${styleName}:${String(disabled)}:${size ?? 'default'}`}</div>
  ),
}));
vi.mock('../components/ClipGallery', () => ({
  ClipGallery: ({
    onEditClip,
  }: {
    onEditClip?: (clip: { created_at: number; has_transcript: boolean; name: string; project?: string; url: string }) => void;
  }) => (
    <div>
      <button onClick={() => onEditClip?.({ created_at: 1, has_transcript: true, name: 'clip-1.mp4', project: 'proj-1', url: '/clip-1.mp4' })}>
        Open Subtitle Clip
      </button>
    </div>
  ),
}));
vi.mock('../components/ThreeCanvas', () => ({ default: () => <div>ThreeCanvas</div> }));
vi.mock('../components/Editor', () => ({
  Editor: ({ mode, targetClip }: { mode: string; targetClip?: { name?: string } | null }) => (
    <div>{`Editor:${mode}:${targetClip?.name ?? 'none'}`}</div>
  ),
}));
vi.mock('../components/AutoCutEditor', () => ({ AutoCutEditor: () => <div>AutoCutEditor</div> }));
vi.mock('../components/SocialWorkspace', () => ({ SocialWorkspace: () => <div>SocialWorkspace</div> }));
vi.mock('../components/SocialComposePage', () => ({ SocialComposePage: () => <div>SocialComposePage</div> }));
vi.mock('../components/SubtitleEditor', () => ({
  SubtitleEditor: ({
    lockedToClip,
    targetClip,
  }: {
    lockedToClip?: boolean;
    targetClip?: { name?: string } | null;
  }) => <div>{`SubtitleEditor:${targetClip?.name ?? 'none'}:${String(Boolean(lockedToClip))}`}</div>,
}));
vi.mock('../components/ui/ConnectionChip', () => ({
  ConnectionChip: ({ status }: { status: string }) => <div>{`Connection:${status}`}</div>,
}));

beforeEach(async () => {
  localStorage.clear();
  window.history.replaceState({}, '', '/');
  document.documentElement.removeAttribute('data-theme');
  await i18n.changeLanguage('en');
  toggleThemeMock.mockClear();
  useWebSocketMock.mockClear();
  resetJobStoreMock.mockClear();
  resilientAuthState.backendAuthStatus = 'fresh';
  resilientAuthState.canAccessApp = true;
  resilientAuthState.canUseBackend = true;
  resilientAuthState.error = null;
  resilientAuthState.identityKey = 'user-1';
  resilientAuthState.isOnline = true;
  resilientAuthState.notice = null;
  resilientAuthState.pauseReason = null;
  resilientAuthState.showUserMenu = true;
  resilientAuthState.status = 'authenticated';
  resilientAuthState.tokenExpiresAt = null;
});

describe('App navigation and workspace restoration', () => {
  it('restores the saved mode and persists navigation changes', async () => {
    localStorage.setItem(AUTH_IDENTITY_STORAGE_KEY, 'user-1');
    localStorage.setItem(APP_STATE_STORAGE_KEY, JSON.stringify({ viewMode: 'subtitle', editingClip: null, subtitleTargetClip: null }));

    render(<App />);

    expect(await screen.findByText('SubtitleEditor:none:false')).toBeInTheDocument();
    expect(document.documentElement).toHaveAttribute('data-theme', 'dark');
    expect(useWebSocketMock).toHaveBeenCalledWith(true);

    fireEvent.click(screen.getByRole('button', { name: /configure/i }));
    expect(await screen.findByText('HoloTerminal')).toBeInTheDocument();
    expect(screen.getByText('SubtitlePreview:TIKTOK:false:tall')).toBeInTheDocument();

    await waitFor(() => {
      expect(JSON.parse(localStorage.getItem(APP_STATE_STORAGE_KEY) ?? '{}')).toEqual({
        editingClip: null,
        subtitleTargetClip: null,
        viewMode: 'config',
      });
    });
  });

  it('renders config workspace in form, preview, logs, queue order', async () => {
    const { container } = render(<App />);

    await screen.findByText('HoloTerminal');

    const content = container.textContent ?? '';
    expect(content.indexOf('Change Style')).toBeLessThan(content.indexOf('SubtitlePreview:TIKTOK:false:tall'));
    expect(content.indexOf('SubtitlePreview:TIKTOK:false:tall')).toBeLessThan(content.indexOf('HoloTerminal'));
    expect(content.indexOf('HoloTerminal')).toBeLessThan(content.indexOf('JobQueue'));
    expect(screen.getByText('Danger Zone')).toBeInTheDocument();
    expect(screen.queryByText(/Preview Snapshot/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Seçilen kombinasyonun kısa görünümü/i)).not.toBeInTheDocument();
  });

  it('opens the locked subtitle editor for gallery edit actions', async () => {
    render(<App />);

    fireEvent.click(await screen.findByRole('button', { name: /open subtitle clip/i }));
    expect(await screen.findByText('SubtitleEditor:clip-1.mp4:true')).toBeInTheDocument();

    await waitFor(() => {
      expect(JSON.parse(localStorage.getItem(APP_STATE_STORAGE_KEY) ?? '{}')).toEqual({
        editingClip: null,
        subtitleTargetClip: {
          created_at: 1,
          has_transcript: true,
          name: 'clip-1.mp4',
          project: 'proj-1',
          resolved_project_id: null,
          transcript_status: 'ready',
          url: '/clip-1.mp4',
        },
        viewMode: 'subtitle',
      });
    });
  });

  it('switches to the auto cut page from the main navigation', async () => {
    render(<App />);

    fireEvent.click(screen.getByRole('button', { name: /auto cut/i }));
    expect(await screen.findByText('AutoCutEditor')).toBeInTheDocument();

    await waitFor(() => {
      expect(JSON.parse(localStorage.getItem(APP_STATE_STORAGE_KEY) ?? '{}')).toEqual({
        editingClip: null,
        subtitleTargetClip: null,
        viewMode: 'manual',
      });
    });
  });

  it('switches to the social page from the main navigation', async () => {
    render(<App />);

    const navigation = screen.getByRole('navigation', { name: /main navigation/i });
    fireEvent.click(within(navigation).getByRole('button', { name: /^social$/i }));
    expect(await screen.findByText('SocialWorkspace')).toBeInTheDocument();

    await waitFor(() => {
      expect(window.location.pathname).toBe('/social');
      expect(window.location.search).toBe('');
      expect(JSON.parse(localStorage.getItem(APP_STATE_STORAGE_KEY) ?? '{}')).toEqual({
        editingClip: null,
        subtitleTargetClip: null,
        viewMode: 'social',
      });
    });
  });

  it('opens social compose when share deep-link contains clip params without a tab', async () => {
    window.history.replaceState({}, '', '/?project_id=proj-1&clip_name=clip-1.mp4');

    render(<App />);

    expect(await screen.findByText('SocialComposePage')).toBeInTheDocument();
    await waitFor(() => {
      expect(window.location.pathname).toBe('/social-compose');
      expect(window.location.search).toBe('?project_id=proj-1&clip_name=clip-1.mp4');
      expect(JSON.parse(localStorage.getItem(APP_STATE_STORAGE_KEY) ?? '{}')).toEqual({
        editingClip: null,
        subtitleTargetClip: null,
        viewMode: 'social_compose',
      });
    });
  });

  it('clears social compose clip context when navigating away to other views', async () => {
    window.history.replaceState({}, '', '/social-compose?project_id=proj-1&clip_name=clip-1.mp4');

    render(<App />);

    expect(await screen.findByText('SocialComposePage')).toBeInTheDocument();

    const navigation = screen.getByRole('navigation', { name: /main navigation/i });

    fireEvent.click(within(navigation).getByRole('button', { name: /^social$/i }));
    await waitFor(() => {
      expect(window.location.pathname).toBe('/social');
      expect(window.location.search).toBe('');
    });

    fireEvent.click(within(navigation).getByRole('button', { name: /auto cut/i }));
    await waitFor(() => {
      expect(window.location.pathname).toBe('/');
      expect(window.location.search).toBe('?tab=manual');
    });

    fireEvent.click(within(navigation).getByRole('button', { name: /subtitle edit/i }));
    await waitFor(() => {
      expect(window.location.pathname).toBe('/');
      expect(window.location.search).toBe('?tab=subtitle');
    });

    fireEvent.click(within(navigation).getByRole('button', { name: /configure/i }));
    await waitFor(() => {
      expect(window.location.pathname).toBe('/');
      expect(window.location.search).toBe('');
    });
  });

  it('renders Turkish navigation and form labels in tr locale', async () => {
    await i18n.changeLanguage('tr');

    render(<App />);

    expect(screen.getByRole('button', { name: 'YAPILANDIR' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'OTOMATİK KES' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'ALTYAZI DÜZENLE' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'SOSYAL' })).toBeInTheDocument();
  });
});

describe('App auth and fallback rendering', () => {
  it('clears locked subtitle targets when opening subtitle mode from navigation', async () => {
    localStorage.setItem(AUTH_IDENTITY_STORAGE_KEY, 'user-1');
    localStorage.setItem(APP_STATE_STORAGE_KEY, JSON.stringify({
      editingClip: null,
      subtitleTargetClip: { created_at: 1, has_transcript: true, name: 'clip-1.mp4', project: 'proj-1', url: '/clip-1.mp4' },
      viewMode: 'subtitle',
    }));

    render(<App />);

    expect(await screen.findByText('SubtitleEditor:clip-1.mp4:true')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /subtitle edit/i }));
    expect(await screen.findByText('SubtitleEditor:none:false')).toBeInTheDocument();
  });

  it('normalizes stored subtitle targets that predate transcript status fields', async () => {
    localStorage.setItem(AUTH_IDENTITY_STORAGE_KEY, 'user-1');
    localStorage.setItem(APP_STATE_STORAGE_KEY, JSON.stringify({
      editingClip: null,
      subtitleTargetClip: { created_at: 1, has_transcript: true, name: 'clip-1.mp4', project: 'proj-1', url: '/clip-1.mp4' },
      viewMode: 'subtitle',
    }));

    render(<App />);

    expect(await screen.findByText('SubtitleEditor:clip-1.mp4:true')).toBeInTheDocument();
    await waitFor(() => {
      expect(JSON.parse(localStorage.getItem(APP_STATE_STORAGE_KEY) ?? '{}')).toEqual({
        editingClip: null,
        subtitleTargetClip: {
          created_at: 1,
          has_transcript: true,
          name: 'clip-1.mp4',
          project: 'proj-1',
          resolved_project_id: null,
          transcript_status: 'ready',
          url: '/clip-1.mp4',
        },
        viewMode: 'subtitle',
      });
    });
  });

  it('shows offline fallback banner and hides the user menu when auth falls back to cache', async () => {
    resilientAuthState.backendAuthStatus = 'paused';
    resilientAuthState.notice = {
      message: 'Onbellekteki oturum kullaniliyor.',
      title: 'Offline mod',
      tone: 'warning',
    };
    resilientAuthState.showUserMenu = false;
    resilientAuthState.pauseReason = 'network_offline';
    resilientAuthState.status = 'offline_authenticated';

    render(<App />);

    expect(await screen.findByText('Onbellekteki oturum kullaniliyor.')).toBeInTheDocument();
    expect(screen.getByText('OFFLINE_SESSION')).toBeInTheDocument();
    expect(screen.queryByText('UserButton')).not.toBeInTheDocument();
  });

  it('keeps the user menu visible while signed in but backend requests are paused', async () => {
    resilientAuthState.backendAuthStatus = 'paused';
    resilientAuthState.canUseBackend = false;
    resilientAuthState.notice = {
      message: 'Oturum yenilenemedi, korumali islemler beklemeye alindi.',
      title: 'Oturum yenileme gerekli',
      tone: 'warning',
    };
    resilientAuthState.pauseReason = 'token_expired';

    render(<App />);

    expect(await screen.findByText('Oturum yenilenemedi, korumali islemler beklemeye alindi.')).toBeInTheDocument();
    expect(screen.getByText('UserButton')).toBeInTheDocument();
    expect(screen.queryByText('AUTH_FALLBACK')).not.toBeInTheDocument();
    expect(useWebSocketMock).toHaveBeenCalledWith(false);
  });
});

describe('App identity reset handling', () => {
  it('clears user-scoped persisted state when the authenticated identity changes', async () => {
    window.history.replaceState({}, '', '/');
    localStorage.setItem(AUTH_IDENTITY_STORAGE_KEY, 'user-legacy');
    localStorage.setItem(APP_STATE_STORAGE_KEY, JSON.stringify({
      editingClip: { created_at: 1, has_transcript: true, name: 'clip-1.mp4', project: 'proj-1', url: '/clip-1.mp4' },
      subtitleTargetClip: null,
      viewMode: 'subtitle',
    }));
    localStorage.setItem(AUTH_SNAPSHOT_STORAGE_KEY, JSON.stringify({ isSignedIn: true }));
    localStorage.setItem(JOB_HISTORY_STORAGE_KEY, JSON.stringify({ version: 1, jobs: [], clipReadyByJob: {}, jobHistoryExpiresAt: null, terminalHistoryCutoffAt: 1 }));
    localStorage.setItem('godtier-auto-cut-session', JSON.stringify({ projectId: 'proj-1' }));
    localStorage.setItem('godtier-editor-master-session', JSON.stringify({ projectId: 'proj-1' }));
    localStorage.setItem('godtier-editor-clip-session:proj-1:clip-1.mp4', JSON.stringify({ projectId: 'proj-1' }));
    localStorage.setItem('social-share-buffer:proj-1:clip-1.mp4', JSON.stringify({ youtube_shorts: { title: 'draft' } }));
    resilientAuthState.identityKey = 'user-2';

    render(<App />);

    await waitFor(() => {
      expect(localStorage.getItem(AUTH_IDENTITY_STORAGE_KEY)).toBe('user-2');
      expect(localStorage.getItem(AUTH_SNAPSHOT_STORAGE_KEY)).toBeNull();
      expect(localStorage.getItem(JOB_HISTORY_STORAGE_KEY)).toBeNull();
      expect(localStorage.getItem('godtier-auto-cut-session')).toBeNull();
      expect(localStorage.getItem('godtier-editor-master-session')).toBeNull();
      expect(localStorage.getItem('godtier-editor-clip-session:proj-1:clip-1.mp4')).toBeNull();
      expect(localStorage.getItem('social-share-buffer:proj-1:clip-1.mp4')).toBeNull();
      expect(JSON.parse(localStorage.getItem(APP_STATE_STORAGE_KEY) ?? '{}')).toEqual({
        editingClip: null,
        subtitleTargetClip: null,
        viewMode: 'config',
      });
    });

    expect(resetJobStoreMock).toHaveBeenCalledTimes(1);
  });
});
