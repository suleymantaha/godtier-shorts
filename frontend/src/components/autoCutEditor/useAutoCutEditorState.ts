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

export function useAutoCutEditorState(initialSession: StoredAutoCutSession | null) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [localSrc, setLocalSrc] = useState<string | null>(null);
  const [projectId, setProjectId] = useState<string | undefined>(initialSession?.projectId);
  const [currentJobId, setCurrentJobId] = useState<string | null>(initialSession?.currentJobId ?? null);
  const [pendingOutputUrl, setPendingOutputUrl] = useState<string | null>(null);
  const [requestError, setRequestError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [startTime, setStartTime] = useState(initialSession?.startTime ?? 0);
  const [endTime, setEndTime] = useState(initialSession?.endTime ?? 60);
  const [duration, setDuration] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [style, setStyle] = useState<StyleName>(initialSession?.style ?? 'TIKTOK');
  const [animationType, setAnimationType] = useState<SubtitleAnimationType>(initialSession?.animationType ?? 'default');
  const [layout, setLayout] = useState<RequestedSubtitleLayout>(
    initialSession?.layout === 'single' || initialSession?.layout === 'split' ? initialSession.layout : 'auto',
  );
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
