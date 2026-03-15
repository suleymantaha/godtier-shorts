import {
  useCallback,
  type ChangeEvent,
  type Dispatch,
  type RefObject,
  type SetStateAction,
  type SyntheticEvent,
} from 'react';

import type { StyleName, SubtitleAnimationType } from '../../config/subtitleStyles';
import { editorApi } from '../../api/client';
import {
  buildAutoCutUploadPayload,
  getMarkerAdditionResult,
  getRangeForLoadedMetadata,
} from './helpers';

interface AutoCutEditorActionParams {
  animationType: SubtitleAnimationType;
  cutAsShort: boolean;
  duration: number;
  endTime: number;
  fetchJobs: () => Promise<void>;
  fileInputRef: RefObject<HTMLInputElement | null>;
  markers: number[];
  numClips: number;
  selectedFile: File | null;
  setCurrentJobId: Dispatch<SetStateAction<string | null>>;
  setDuration: Dispatch<SetStateAction<number>>;
  setEndTime: Dispatch<SetStateAction<number>>;
  setIsSubmitting: Dispatch<SetStateAction<boolean>>;
  setKesFeedback: Dispatch<SetStateAction<string | null>>;
  setLocalSrc: Dispatch<SetStateAction<string | null>>;
  setMarkers: Dispatch<SetStateAction<number[]>>;
  setNumClips: Dispatch<SetStateAction<number>>;
  setPendingOutputUrl: Dispatch<SetStateAction<string | null>>;
  setProjectId: Dispatch<SetStateAction<string | undefined>>;
  setRequestError: Dispatch<SetStateAction<string | null>>;
  setSelectedFile: Dispatch<SetStateAction<File | null>>;
  setStartTime: Dispatch<SetStateAction<number>>;
  skipSubtitles: boolean;
  startTime: number;
  style: StyleName;
  videoRef: RefObject<HTMLVideoElement | null>;
}

type AutoCutVideoActionParams = Pick<
  AutoCutEditorActionParams,
  'endTime' | 'fileInputRef' | 'markers' | 'setDuration' | 'setEndTime' | 'setKesFeedback' | 'setMarkers' | 'setNumClips' | 'setStartTime' | 'startTime' | 'videoRef'
>;

type AutoCutFileSelectionParams = Pick<
  AutoCutEditorActionParams,
  'setCurrentJobId' | 'setDuration' | 'setKesFeedback' | 'setLocalSrc' | 'setMarkers' | 'setPendingOutputUrl' | 'setProjectId' | 'setRequestError' | 'setSelectedFile'
>;

type AutoCutRenderSubmissionParams = Pick<
  AutoCutEditorActionParams,
  'animationType' | 'cutAsShort' | 'duration' | 'endTime' | 'fetchJobs' | 'markers' | 'numClips' | 'selectedFile' | 'setCurrentJobId' | 'setIsSubmitting' | 'setPendingOutputUrl' | 'setProjectId' | 'setRequestError' | 'skipSubtitles' | 'startTime' | 'style'
>;

function toggleVideoPlayback(video: HTMLVideoElement | null) {
  if (!video) {
    return;
  }

  if (video.paused) {
    void video.play();
    return;
  }

  video.pause();
}

function replaceLocalVideoSource(file: File, setLocalSrc: Dispatch<SetStateAction<string | null>>) {
  setLocalSrc((previousUrl) => {
    if (previousUrl) {
      URL.revokeObjectURL(previousUrl);
    }

    return URL.createObjectURL(file);
  });
}

function updateRangeForLoadedVideo(
  mediaDuration: number,
  startTime: number,
  endTime: number,
  setStartTime: Dispatch<SetStateAction<number>>,
  setEndTime: Dispatch<SetStateAction<number>>,
) {
  const range = getRangeForLoadedMetadata(mediaDuration, startTime, endTime);

  setStartTime(range.startTime);
  setEndTime(range.endTime);
}

function applyMarkerAtCurrentTime(
  video: HTMLVideoElement | null,
  startTime: number,
  endTime: number,
  markers: number[],
  setMarkers: Dispatch<SetStateAction<number[]>>,
  setKesFeedback: Dispatch<SetStateAction<string | null>>,
) {
  setKesFeedback(null);
  if (!video) {
    setKesFeedback('Video yukleniyor...');
    return;
  }

  const result = getMarkerAdditionResult({
    currentTime: video.currentTime,
    endTime,
    markers,
    startTime,
  });

  setMarkers(result.markers);
  setKesFeedback(result.feedback);
  if (result.markers !== markers) {
    window.setTimeout(() => setKesFeedback(null), 2000);
  }
}

async function submitAutoCutRender({
  animationType,
  cutAsShort,
  duration,
  endTime,
  fetchJobs,
  markers,
  numClips,
  selectedFile,
  setCurrentJobId,
  setPendingOutputUrl,
  setProjectId,
  skipSubtitles,
  startTime,
  style,
}: Pick<
  AutoCutEditorActionParams,
  | 'animationType'
  | 'cutAsShort'
  | 'duration'
  | 'endTime'
  | 'fetchJobs'
  | 'markers'
  | 'numClips'
  | 'selectedFile'
  | 'setCurrentJobId'
  | 'setPendingOutputUrl'
  | 'setProjectId'
  | 'skipSubtitles'
  | 'startTime'
  | 'style'
>) {
  if (!selectedFile) {
    throw new Error('Once bir video sec.');
  }

  const response = await editorApi.manualCutUpload(selectedFile, buildAutoCutUploadPayload({
    animationType,
    cutAsShort,
    duration,
    endTime,
    markers,
    numClips,
    skipSubtitles,
    startTime,
    style,
  }));

  setProjectId(response.project_id);
  setCurrentJobId(response.job_id);
  setPendingOutputUrl(response.output_url ?? null);
  await fetchJobs();
}

function useAutoCutVideoActions({
  endTime,
  fileInputRef,
  markers,
  setDuration,
  setEndTime,
  setKesFeedback,
  setMarkers,
  setNumClips,
  setStartTime,
  startTime,
  videoRef,
}: AutoCutVideoActionParams) {
  const openFilePicker = useCallback(() => fileInputRef.current?.click(), [fileInputRef]);
  const togglePlay = useCallback(() => toggleVideoPlayback(videoRef.current), [videoRef]);
  const jumpToStart = useCallback(() => {
    if (videoRef.current) {
      videoRef.current.currentTime = startTime;
    }
  }, [startTime, videoRef]);
  const jumpToEnd = useCallback(() => {
    if (videoRef.current) {
      videoRef.current.currentTime = Math.max(startTime, endTime - 3);
    }
  }, [endTime, startTime, videoRef]);
  const removeMarker = useCallback(
    (index: number) => setMarkers((previous) => previous.filter((_, markerIndex) => markerIndex !== index)),
    [setMarkers],
  );
  const updateRange = useCallback((nextStart: number, nextEnd: number) => {
    setStartTime(nextStart);
    setEndTime(nextEnd);
  }, [setEndTime, setStartTime]);
  const updateSelectedClipCount = useCallback((value: string) => {
    setNumClips((current) => Math.min(10, Math.max(1, Number(value) || current || 1)));
  }, [setNumClips]);
  const addCurrentMarker = useCallback(() => {
    applyMarkerAtCurrentTime(videoRef.current, startTime, endTime, markers, setMarkers, setKesFeedback);
  }, [endTime, markers, setKesFeedback, setMarkers, startTime, videoRef]);
  const handleVideoLoadedMetadata = useCallback((event: SyntheticEvent<HTMLVideoElement>) => {
    const mediaDuration = event.currentTarget.duration;
    setDuration(mediaDuration);
    updateRangeForLoadedVideo(mediaDuration, startTime, endTime, setStartTime, setEndTime);
  }, [endTime, setDuration, setEndTime, setStartTime, startTime]);

  return {
    addCurrentMarker,
    handleVideoLoadedMetadata,
    jumpToEnd,
    jumpToStart,
    openFilePicker,
    removeMarker,
    togglePlay,
    updateRange,
    updateSelectedClipCount,
  };
}

function useAutoCutFileSelection({
  setCurrentJobId,
  setDuration,
  setKesFeedback,
  setLocalSrc,
  setMarkers,
  setPendingOutputUrl,
  setProjectId,
  setRequestError,
  setSelectedFile,
}: AutoCutFileSelectionParams) {
  const handleFileSelect = useCallback((event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    setSelectedFile(file);
    setProjectId(undefined);
    setCurrentJobId(null);
    setDuration(0);
    setPendingOutputUrl(null);
    setRequestError(null);
    setKesFeedback(null);
    setMarkers([]);
    replaceLocalVideoSource(file, setLocalSrc);
  }, [
    setCurrentJobId,
    setDuration,
    setKesFeedback,
    setLocalSrc,
    setMarkers,
    setPendingOutputUrl,
    setProjectId,
    setRequestError,
    setSelectedFile,
  ]);

  return { handleFileSelect };
}

function useAutoCutRenderSubmission({
  animationType,
  cutAsShort,
  duration,
  endTime,
  fetchJobs,
  markers,
  numClips,
  selectedFile,
  setCurrentJobId,
  setIsSubmitting,
  setPendingOutputUrl,
  setProjectId,
  setRequestError,
  skipSubtitles,
  startTime,
  style,
}: AutoCutRenderSubmissionParams) {
  const handleRender = useCallback(async () => {
    if (!selectedFile) {
      setRequestError('Once bir video sec.');
      return;
    }

    if (endTime <= startTime) {
      setRequestError('Bitis zamani baslangictan buyuk olmali.');
      return;
    }

    setIsSubmitting(true);
    setRequestError(null);
    setPendingOutputUrl(null);

    try {
      await submitAutoCutRender({
        animationType,
        cutAsShort,
        duration,
        endTime,
        fetchJobs,
        markers,
        numClips,
        selectedFile,
        setCurrentJobId,
        setPendingOutputUrl,
        setProjectId,
        skipSubtitles,
        startTime,
        style,
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Otomatik manual cut baslatilamadi.';
      setRequestError(message);
    } finally {
      setIsSubmitting(false);
    }
  }, [animationType, cutAsShort, duration, endTime, fetchJobs, markers, numClips, selectedFile, setCurrentJobId, setIsSubmitting, setPendingOutputUrl, setProjectId, setRequestError, skipSubtitles, startTime, style]);

  return { handleRender };
}

export function useAutoCutEditorActions(params: AutoCutEditorActionParams) {
  return {
    ...useAutoCutFileSelection(params),
    ...useAutoCutVideoActions(params),
    ...useAutoCutRenderSubmission(params),
  };
}
