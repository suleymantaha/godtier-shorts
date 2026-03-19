import { useEffect } from 'react';

import { useJobStore } from '../../store/useJobStore';

interface SyncActiveJobParams {
  currentJobId: string | null;
  fetchJobs: () => Promise<void>;
  setCurrentJobId: React.Dispatch<React.SetStateAction<string | null>>;
  setPendingOutputUrl: React.Dispatch<React.SetStateAction<string | null>>;
  setProjectId: React.Dispatch<React.SetStateAction<string | undefined>>;
  storageKey: string;
}

interface PersistSessionParams {
  animationType: string;
  currentJobId: string | null;
  endTime: number;
  layout: string;
  processing: boolean;
  projectId?: string;
  startTime: number;
  storageKey: string;
  style: string;
}

export function useSyncActiveAutoCutJob({
  currentJobId,
  fetchJobs,
  setCurrentJobId,
  setPendingOutputUrl,
  setProjectId,
  storageKey,
}: SyncActiveJobParams) {
  useEffect(() => {
    const syncJobs = async () => {
      await fetchJobs();
      if (!currentJobId) {
        return;
      }

      const jobExists = useJobStore.getState().jobs.some((job) => job.job_id === currentJobId);
      if (!jobExists) {
        setCurrentJobId(null);
        setProjectId(undefined);
        setPendingOutputUrl(null);
        window.localStorage.removeItem(storageKey);
      }
    };

    void syncJobs();
  }, [currentJobId, fetchJobs, setCurrentJobId, setPendingOutputUrl, setProjectId, storageKey]);
}

export function usePersistAutoCutSession({
  animationType,
  currentJobId,
  endTime,
  layout,
  processing,
  projectId,
  startTime,
  storageKey,
  style,
}: PersistSessionParams) {
  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }

    if (processing && currentJobId) {
      window.localStorage.setItem(storageKey, JSON.stringify({ animationType, currentJobId, endTime, layout, projectId, startTime, style }));
      return;
    }

    window.localStorage.removeItem(storageKey);
  }, [animationType, currentJobId, endTime, layout, processing, projectId, startTime, storageKey, style]);
}

export function useRevokeLocalVideoUrl(localSrc: string | null) {
  useEffect(() => {
    return () => {
      if (localSrc) {
        URL.revokeObjectURL(localSrc);
      }
    };
  }, [localSrc]);
}
