import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import App from '../App';
import { APP_STATE_STORAGE_KEY } from '../app/helpers';

const getTokenMock = vi.fn().mockResolvedValue('jwt-token');
const toggleThemeMock = vi.fn();
const useWebSocketMock = vi.fn();

vi.mock('@clerk/clerk-react', () => ({
  SignedIn: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  SignedOut: () => null,
  SignIn: () => <div>SignIn</div>,
  UserButton: () => <div>UserButton</div>,
  useAuth: () => ({ getToken: getTokenMock, isLoaded: true, isSignedIn: true }),
}));

vi.mock('../hooks/useWebSocket', () => ({
  useWebSocket: (...args: unknown[]) => useWebSocketMock(...args),
}));

vi.mock('../store/useJobStore', () => ({
  useJobStore: (selector: (state: { wsStatus: string }) => unknown) => selector({ wsStatus: 'connected' }),
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

vi.mock('../components/HoloTerminal', () => ({ HoloTerminal: () => <div>HoloTerminal</div> }));
vi.mock('../components/JobQueue', () => ({ JobQueue: () => <div>JobQueue</div> }));
vi.mock('../components/SubtitlePreview', () => ({
  SubtitlePreview: ({ disabled, styleName }: { disabled: boolean; styleName: string }) => (
    <div>{`SubtitlePreview:${styleName}:${String(disabled)}`}</div>
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

describe('App', () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute('data-theme');
    getTokenMock.mockClear();
    toggleThemeMock.mockClear();
    useWebSocketMock.mockClear();
  });

  it('restores the saved mode and persists navigation changes', async () => {
    localStorage.setItem(APP_STATE_STORAGE_KEY, JSON.stringify({ viewMode: 'subtitle', editingClip: null, subtitleTargetClip: null }));

    render(<App />);

    expect(await screen.findByText('SubtitleEditor:none:false')).toBeInTheDocument();
    expect(document.documentElement).toHaveAttribute('data-theme', 'dark');
    expect(useWebSocketMock).toHaveBeenCalledWith(true);

    fireEvent.click(screen.getByRole('button', { name: /configure/i }));
    expect(await screen.findByText('HoloTerminal')).toBeInTheDocument();

    await waitFor(() => {
      expect(getTokenMock).toHaveBeenCalled();
      expect(JSON.parse(localStorage.getItem(APP_STATE_STORAGE_KEY) ?? '{}')).toEqual({
        editingClip: null,
        subtitleTargetClip: null,
        viewMode: 'config',
      });
    });
  });

  it('opens the locked subtitle editor for gallery edit actions', async () => {
    render(<App />);

    fireEvent.click(await screen.findByRole('button', { name: /open subtitle clip/i }));
    expect(await screen.findByText('SubtitleEditor:clip-1.mp4:true')).toBeInTheDocument();
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

  it('clears locked subtitle targets when opening subtitle mode from navigation', async () => {
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
});
