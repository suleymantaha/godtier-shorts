import { useCallback, useEffect, useRef, useState, type Dispatch, type MutableRefObject, type SetStateAction } from 'react';

import type { Segment } from '../../types';
import { resolveLoadedEndTime, resolveTranscriptDuration } from './helpers';

export function useSuccessMessageTimeout(
  successMessage: string | null,
  setSuccessMessage: Dispatch<SetStateAction<string | null>>,
) {
  useEffect(() => {
    if (!successMessage) {
      return;
    }

    const timer = window.setTimeout(() => setSuccessMessage(null), 5000);
    return () => window.clearTimeout(timer);
  }, [setSuccessMessage, successMessage]);
}

export function useTranscriptDurationEffect({
  duration,
  rangeTouchedSelectionRef,
  selectionKey,
  setDuration,
  setEndTime,
  transcript,
}: {
  duration: number;
  rangeTouchedSelectionRef: MutableRefObject<string | null>;
  selectionKey: string | null;
  setDuration: Dispatch<SetStateAction<number>>;
  setEndTime: Dispatch<SetStateAction<number>>;
  transcript: Segment[];
}) {
  useEffect(() => {
    if (transcript.length === 0 || duration !== 0) {
      return;
    }

    const nextDuration = resolveTranscriptDuration(transcript);
    setDuration(nextDuration);
    if (rangeTouchedSelectionRef.current !== selectionKey) {
      setEndTime(Math.min(60, nextDuration));
    }
  }, [duration, rangeTouchedSelectionRef, selectionKey, setDuration, setEndTime, transcript]);
}

export function useSubtitlePlayback({
  setCurrentTime,
  setDuration,
  setEndTime,
  videoRef,
}: {
  setCurrentTime: Dispatch<SetStateAction<number>>;
  setDuration: Dispatch<SetStateAction<number>>;
  setEndTime: Dispatch<SetStateAction<number>>;
  videoRef: MutableRefObject<HTMLVideoElement | null>;
}) {
  const handleTimeUpdate = useCallback(() => {
    if (videoRef.current) {
      setCurrentTime(videoRef.current.currentTime);
    }
  }, [setCurrentTime, videoRef]);

  const togglePlay = useCallback(() => {
    if (!videoRef.current) {
      return;
    }

    if (videoRef.current.paused) {
      void videoRef.current.play();
    } else {
      videoRef.current.pause();
    }
  }, [videoRef]);

  const handleLoadedMetadata = useCallback((duration: number) => {
    setDuration(duration);
    setEndTime((previousEndTime) => resolveLoadedEndTime(duration, previousEndTime));
  }, [setDuration, setEndTime]);

  return { handleLoadedMetadata, handleTimeUpdate, togglePlay };
}

export function useSubtitleRangeChangeAction({
  endTime,
  markRangeTouched,
  setCurrentTime,
  setEndTime,
  setStartTime,
  startTime,
  videoRef,
}: {
  endTime: number;
  markRangeTouched: () => void;
  setCurrentTime: Dispatch<SetStateAction<number>>;
  setEndTime: Dispatch<SetStateAction<number>>;
  setStartTime: Dispatch<SetStateAction<number>>;
  startTime: number;
  videoRef: MutableRefObject<HTMLVideoElement | null>;
}) {
  return useCallback((nextStartTime: number, nextEndTime: number) => {
    markRangeTouched();
    setStartTime(nextStartTime);
    setEndTime(nextEndTime);

    const seekTime = nextStartTime !== startTime
      ? nextStartTime
      : nextEndTime !== endTime
        ? nextEndTime
        : nextEndTime;
    if (videoRef.current) {
      videoRef.current.currentTime = seekTime;
    }
    setCurrentTime(seekTime);
  }, [
    endTime,
    markRangeTouched,
    setCurrentTime,
    setEndTime,
    setStartTime,
    startTime,
    videoRef,
  ]);
}

export function useRangeSelectionResetEffect({
  clearRangeReadySelection,
  selectionKey,
  setCurrentJobId,
  setCurrentTime,
  setDuration,
  setEndTime,
  setError,
  setStartTime,
  setSuccessMessage,
}: {
  clearRangeReadySelection: () => void;
  selectionKey: string | null;
  setCurrentJobId: Dispatch<SetStateAction<string | null>>;
  setCurrentTime: Dispatch<SetStateAction<number>>;
  setDuration: Dispatch<SetStateAction<number>>;
  setEndTime: Dispatch<SetStateAction<number>>;
  setError: Dispatch<SetStateAction<string | null>>;
  setStartTime: Dispatch<SetStateAction<number>>;
  setSuccessMessage: Dispatch<SetStateAction<string | null>>;
}) {
  const previousSelectionKeyRef = useRef<string | null>(null);

  useEffect(() => {
    if (previousSelectionKeyRef.current === selectionKey) {
      return;
    }

    previousSelectionKeyRef.current = selectionKey;
    clearRangeReadySelection();
    setStartTime(0);
    setEndTime(60);
    setDuration(0);
    setCurrentTime(0);
    setCurrentJobId(null);
    setError(null);
    setSuccessMessage(null);
  }, [
    clearRangeReadySelection,
    selectionKey,
    setCurrentJobId,
    setCurrentTime,
    setDuration,
    setEndTime,
    setError,
    setStartTime,
    setSuccessMessage,
  ]);
}

export function useStableRangeReady({
  rangeReadyCandidate,
  selectionKey,
}: {
  rangeReadyCandidate: boolean;
  selectionKey: string | null;
}) {
  const [rangeReadySelectionKey, setRangeReadySelectionKey] = useState<string | null>(null);

  useEffect(() => {
    if (selectionKey && rangeReadyCandidate) {
      setRangeReadySelectionKey(selectionKey);
    }
  }, [rangeReadyCandidate, selectionKey]);

  const clearRangeReadySelection = useCallback(() => {
    setRangeReadySelectionKey(null);
  }, []);

  return {
    clearRangeReadySelection,
    rangeReady: Boolean(selectionKey) && rangeReadySelectionKey === selectionKey,
  };
}
