import { startTransition, useCallback, useEffect, useState } from 'react';

import { syncIdentityBoundary } from '../auth/isolation';
import { useWebSocket } from '../hooks/useWebSocket';
import { useJobStore } from '../store/useJobStore';
import { useLocaleStore } from '../store/useLocaleStore';
import { useThemeStore } from '../store/useThemeStore';
import type { Clip } from '../types';
import type { SubtitleAnimationType } from '../config/subtitleStyles';
import {
  normalizeStoredClip,
  persistAppState,
  readAppState,
  readQueryViewMode,
  syncViewModeToUrl,
  type AppViewMode,
} from './helpers';

type SetClipState = React.Dispatch<React.SetStateAction<Clip | null>>;
type SetViewModeState = React.Dispatch<React.SetStateAction<AppViewMode>>;
type SetSubtitleNonceState = React.Dispatch<React.SetStateAction<number>>;

function clearAppShellSelection(setEditingClip: SetClipState, setSubtitleTargetClip: SetClipState) {
  setEditingClip(null);
  setSubtitleTargetClip(null);
}

function useAppShellNavigation({
  setEditingClip,
  setSubtitleSessionNonce,
  setSubtitleTargetClip,
  setViewMode,
}: {
  setEditingClip: SetClipState;
  setSubtitleSessionNonce: SetSubtitleNonceState;
  setSubtitleTargetClip: SetClipState;
  setViewMode: SetViewModeState;
}) {
  const openViewMode = useCallback((nextMode: AppViewMode) => {
    setViewMode(nextMode);
    clearAppShellSelection(setEditingClip, setSubtitleTargetClip);
  }, [setEditingClip, setSubtitleTargetClip, setViewMode]);

  const openConfig = useCallback(() => openViewMode('config'), [openViewMode]);
  const openManual = useCallback(() => openViewMode('manual'), [openViewMode]);
  const openSocial = useCallback(() => openViewMode('social'), [openViewMode]);
  const openSocialCompose = useCallback(() => openViewMode('social_compose'), [openViewMode]);
  const openSubtitle = useCallback(() => {
    openViewMode('subtitle');
    setSubtitleSessionNonce((nonce) => nonce + 1);
  }, [openViewMode, setSubtitleSessionNonce]);
  const openClipSubtitleEditor = useCallback((clip: Clip) => {
    setViewMode('subtitle');
    setEditingClip(null);
    setSubtitleTargetClip(normalizeStoredClip({ ...clip }));
    setSubtitleSessionNonce((nonce) => nonce + 1);
  }, [setEditingClip, setSubtitleSessionNonce, setSubtitleTargetClip, setViewMode]);

  return {
    openClipSubtitleEditor,
    openConfig,
    openManual,
    openSocialCompose,
    openSocial,
    openSubtitle,
  };
}

function useThemeSyncEffect(theme: string) {
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);
}

function useIdentityBoundaryResetEffect({
  identityKey,
  setEditingClip,
  setSubtitleSessionNonce,
  setSubtitleTargetClip,
  setViewMode,
}: {
  identityKey: string | null;
  setEditingClip: SetClipState;
  setSubtitleSessionNonce: SetSubtitleNonceState;
  setSubtitleTargetClip: SetClipState;
  setViewMode: SetViewModeState;
}) {
  useEffect(() => {
    if (!syncIdentityBoundary(identityKey)) {
      return;
    }

    const requestedMode = readQueryViewMode(window.location.search);
    const resetTimer = window.setTimeout(() => {
      startTransition(() => {
        // Keep explicit deep-link tabs (e.g. ?tab=social) after identity boundary sync.
        setViewMode(requestedMode ?? 'config');
        clearAppShellSelection(setEditingClip, setSubtitleTargetClip);
        setSubtitleSessionNonce(0);
      });
      useJobStore.getState?.().reset?.();
    }, 0);

    return () => window.clearTimeout(resetTimer);
  }, [identityKey, setEditingClip, setSubtitleSessionNonce, setSubtitleTargetClip, setViewMode]);
}

function usePersistedAppShellStateEffect(
  viewMode: AppViewMode,
  editingClip: Clip | null,
  subtitleTargetClip: Clip | null,
) {
  useEffect(() => {
    persistAppState(viewMode, editingClip, subtitleTargetClip);
    syncViewModeToUrl(viewMode);
  }, [editingClip, subtitleTargetClip, viewMode]);
}

export function useAppShellController(canUseBackend = true, identityKey: string | null = null) {
  useWebSocket(canUseBackend);
  const wsStatus = useJobStore((store) => store.wsStatus);
  const [viewMode, setViewMode] = useState<AppViewMode>(() => readAppState().viewMode);
  const [editingClip, setEditingClip] = useState<Clip | null>(() => readAppState().editingClip);
  const [subtitleTargetClip, setSubtitleTargetClip] = useState<Clip | null>(() => readAppState().subtitleTargetClip);
  const [subtitleSessionNonce, setSubtitleSessionNonce] = useState(0);
  const [currentStyle, setCurrentStyle] = useState('TIKTOK');
  const [currentAnimationType, setCurrentAnimationType] = useState<SubtitleAnimationType>('default');
  const [subtitlesDisabled, setSubtitlesDisabled] = useState(false);
  const { theme, toggleTheme } = useThemeStore();
  const { locale, setLocale } = useLocaleStore();
  const {
    openClipSubtitleEditor,
    openConfig,
    openManual,
    openSocialCompose,
    openSocial,
    openSubtitle,
  } = useAppShellNavigation({
    setEditingClip,
    setSubtitleSessionNonce,
    setSubtitleTargetClip,
    setViewMode,
  });

  const closeEditor = useCallback(() => setEditingClip(null), []);
  const handleAnimationChange = useCallback((animationType: SubtitleAnimationType) => setCurrentAnimationType(animationType), []);
  const handleStyleChange = useCallback((styleName: string) => setCurrentStyle(styleName), []);
  const handleSkipSubtitlesChange = useCallback((disabled: boolean) => setSubtitlesDisabled(disabled), []);

  useThemeSyncEffect(theme);
  useIdentityBoundaryResetEffect({
    identityKey,
    setEditingClip,
    setSubtitleSessionNonce,
    setSubtitleTargetClip,
    setViewMode,
  });
  usePersistedAppShellStateEffect(viewMode, editingClip, subtitleTargetClip);

  return {
    closeEditor,
    currentAnimationType,
    currentStyle,
    editingClip,
    handleAnimationChange,
    handleSkipSubtitlesChange,
    handleStyleChange,
    openClipSubtitleEditor,
    openConfig,
    openManual,
    openSocialCompose,
    openSocial,
    openSubtitle,
    locale,
    setLocale,
    setEditingClip,
    subtitleSessionNonce,
    subtitleTargetClip,
    subtitlesDisabled,
    theme,
    toggleTheme,
    viewMode,
    wsStatus,
  };
}
