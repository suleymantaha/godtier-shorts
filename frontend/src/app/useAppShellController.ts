import { startTransition, useCallback, useEffect, useState } from 'react';

import { syncIdentityBoundary } from '../auth/isolation';
import { useWebSocket } from '../hooks/useWebSocket';
import { useJobStore } from '../store/useJobStore';
import { useLocaleStore } from '../store/useLocaleStore';
import { useThemeStore } from '../store/useThemeStore';
import type { Clip } from '../types';
import { normalizeStoredClip, persistAppState, readAppState, readQueryViewMode, syncViewModeToUrl, type AppViewMode } from './helpers';
import type { SubtitleAnimationType } from '../config/subtitleStyles';

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

  const openConfig = useCallback(() => {
    setViewMode('config');
    setEditingClip(null);
    setSubtitleTargetClip(null);
  }, []);

  const openManual = useCallback(() => {
    setViewMode('manual');
    setEditingClip(null);
    setSubtitleTargetClip(null);
  }, []);

  const openSubtitle = useCallback(() => {
    setViewMode('subtitle');
    setEditingClip(null);
    setSubtitleTargetClip(null);
    setSubtitleSessionNonce((nonce) => nonce + 1);
  }, []);

  const openSocial = useCallback(() => {
    setViewMode('social');
    setEditingClip(null);
    setSubtitleTargetClip(null);
  }, []);

  const openSocialCompose = useCallback(() => {
    setViewMode('social_compose');
    setEditingClip(null);
    setSubtitleTargetClip(null);
  }, []);

  const openClipSubtitleEditor = useCallback((clip: Clip) => {
    setViewMode('subtitle');
    setEditingClip(null);
    setSubtitleTargetClip(normalizeStoredClip({ ...clip }));
    setSubtitleSessionNonce((nonce) => nonce + 1);
  }, []);

  const closeEditor = useCallback(() => setEditingClip(null), []);
  const handleAnimationChange = useCallback((animationType: SubtitleAnimationType) => setCurrentAnimationType(animationType), []);
  const handleStyleChange = useCallback((styleName: string) => setCurrentStyle(styleName), []);
  const handleSkipSubtitlesChange = useCallback((disabled: boolean) => setSubtitlesDisabled(disabled), []);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  useEffect(() => {
    if (!syncIdentityBoundary(identityKey)) {
      return;
    }
    const requestedMode = readQueryViewMode(window.location.search);

    const resetTimer = window.setTimeout(() => {
      startTransition(() => {
        // Keep explicit deep-link tabs (e.g. ?tab=social) after identity boundary sync.
        setViewMode(requestedMode ?? 'config');
        setEditingClip(null);
        setSubtitleTargetClip(null);
        setSubtitleSessionNonce(0);
      });
      useJobStore.getState?.().reset?.();
    }, 0);

    return () => window.clearTimeout(resetTimer);
  }, [identityKey]);

  useEffect(() => {
    persistAppState(viewMode, editingClip, subtitleTargetClip);
    syncViewModeToUrl(viewMode);
  }, [editingClip, subtitleTargetClip, viewMode]);

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
