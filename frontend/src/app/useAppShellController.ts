import { useCallback, useEffect, useState } from 'react';
import { useAuth } from '@clerk/clerk-react';

import { setApiToken } from '../api/client';
import { CLERK_JWT_TEMPLATE } from '../config';
import { useWebSocket } from '../hooks/useWebSocket';
import { useJobStore } from '../store/useJobStore';
import { useThemeStore } from '../store/useThemeStore';
import type { Clip } from '../types';
import { persistAppState, readAppState, type AppViewMode } from './helpers';

export function useAppShellController() {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  useWebSocket(isLoaded && isSignedIn);
  const wsStatus = useJobStore((store) => store.wsStatus);
  const [viewMode, setViewMode] = useState<AppViewMode>(() => readAppState().viewMode);
  const [editingClip, setEditingClip] = useState<Clip | null>(() => readAppState().editingClip);
  const [subtitleTargetClip, setSubtitleTargetClip] = useState<Clip | null>(() => readAppState().subtitleTargetClip);
  const [currentStyle, setCurrentStyle] = useState('TIKTOK');
  const [subtitlesDisabled, setSubtitlesDisabled] = useState(false);
  const { theme, toggleTheme } = useThemeStore();

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
  }, []);

  const openClipSubtitleEditor = useCallback((clip: Clip) => {
    setViewMode('subtitle');
    setEditingClip(null);
    setSubtitleTargetClip(clip);
  }, []);

  const openClipAdvancedEditor = useCallback((clip: Clip) => {
    setEditingClip(clip);
    setSubtitleTargetClip(null);
  }, []);

  const closeEditor = useCallback(() => setEditingClip(null), []);
  const handleStyleChange = useCallback((styleName: string) => setCurrentStyle(styleName), []);
  const handleSkipSubtitlesChange = useCallback((disabled: boolean) => setSubtitlesDisabled(disabled), []);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  useEffect(() => {
    void syncApiToken(getToken, isLoaded, isSignedIn);
  }, [getToken, isLoaded, isSignedIn]);

  useEffect(() => {
    persistAppState(viewMode, editingClip, subtitleTargetClip);
  }, [editingClip, subtitleTargetClip, viewMode]);

  return {
    closeEditor,
    currentStyle,
    editingClip,
    handleSkipSubtitlesChange,
    handleStyleChange,
    openClipAdvancedEditor,
    openClipSubtitleEditor,
    openConfig,
    openManual,
    openSubtitle,
    setEditingClip,
    subtitleTargetClip,
    subtitlesDisabled,
    theme,
    toggleTheme,
    viewMode,
    wsStatus,
  };
}

async function syncApiToken(
  getToken: (options?: { template?: string }) => Promise<string | null>,
  isLoaded: boolean,
  isSignedIn: boolean | undefined,
) {
  if (!isLoaded || !isSignedIn) {
    setApiToken(null);
    return;
  }

  const options = CLERK_JWT_TEMPLATE ? { template: CLERK_JWT_TEMPLATE } : undefined;
  const token = await getToken(options);
  setApiToken(token);
}
