import { useRef, useState } from 'react';

import type { RequestedSubtitleLayout, StyleName, SubtitleAnimationType } from '../../config/subtitleStyles';

export interface StoredAutoCutSession {
  animationType?: SubtitleAnimationType;
  currentJobId?: string | null;
  endTime?: number;
  layout?: RequestedSubtitleLayout;
  projectId?: string;
  startTime?: number;
  style?: StyleName;
}

function resolveInitialLayout(layout: StoredAutoCutSession['layout']): RequestedSubtitleLayout {
  return layout === 'single' || layout === 'split' ? layout : 'auto';
}

function resolveInitialTimingState(initialSession: StoredAutoCutSession | null) {
  return {
    currentJobId: initialSession?.currentJobId ?? null,
    endTime: initialSession?.endTime ?? 60,
    projectId: initialSession?.projectId,
    startTime: initialSession?.startTime ?? 0,
  };
}

function resolveInitialSubtitleState(initialSession: StoredAutoCutSession | null) {
  return {
    animationType: initialSession?.animationType ?? 'default',
    layout: resolveInitialLayout(initialSession?.layout),
    style: initialSession?.style ?? 'TIKTOK',
  };
}

function resolveInitialSessionState(initialSession: StoredAutoCutSession | null) {
  return {
    ...resolveInitialTimingState(initialSession),
    ...resolveInitialSubtitleState(initialSession),
  };
}

export function useAutoCutEditorState(initialSession: StoredAutoCutSession | null) {
  const initialState = resolveInitialSessionState(initialSession);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [localSrc, setLocalSrc] = useState<string | null>(null);
  const [projectId, setProjectId] = useState<string | undefined>(initialState.projectId);
  const [currentJobId, setCurrentJobId] = useState<string | null>(initialState.currentJobId);
  const [pendingOutputUrl, setPendingOutputUrl] = useState<string | null>(null);
  const [requestError, setRequestError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [startTime, setStartTime] = useState(initialState.startTime);
  const [endTime, setEndTime] = useState(initialState.endTime);
  const [duration, setDuration] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [style, setStyle] = useState<StyleName>(initialState.style);
  const [animationType, setAnimationType] = useState<SubtitleAnimationType>(initialState.animationType);
  const [layout, setLayout] = useState<RequestedSubtitleLayout>(initialState.layout);
  const [skipSubtitles, setSkipSubtitles] = useState(false);
  const [cutAsShort, setCutAsShort] = useState(true);
  const [numClips, setNumClips] = useState(3);
  const [markers, setMarkers] = useState<number[]>([]);
  const [kesFeedback, setKesFeedback] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);

  return {
    animationType,
    currentJobId,
    cutAsShort,
    duration,
    endTime,
    fileInputRef,
    isPlaying,
    isSubmitting,
    kesFeedback,
    layout,
    localSrc,
    markers,
    numClips,
    pendingOutputUrl,
    projectId,
    requestError,
    selectedFile,
    setAnimationType,
    setCurrentJobId,
    setCutAsShort,
    setDuration,
    setEndTime,
    setIsPlaying,
    setIsSubmitting,
    setKesFeedback,
    setLayout,
    setLocalSrc,
    setMarkers,
    setNumClips,
    setPendingOutputUrl,
    setProjectId,
    setRequestError,
    setSelectedFile,
    setSkipSubtitles,
    setStartTime,
    setStyle,
    skipSubtitles,
    startTime,
    style,
    videoRef,
  };
}
