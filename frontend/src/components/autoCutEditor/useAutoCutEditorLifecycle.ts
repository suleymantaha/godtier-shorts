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
  currentJobId: string | null;
  endTime: number;
  processing: boolean;
  projectId?: string;
  startTime: number;
  storageKey: string;
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
  currentJobId,
  endTime,
  processing,
  projectId,
  startTime,
  storageKey,
}: PersistSessionParams) {
  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }

    if (processing && currentJobId) {
      window.localStorage.setItem(storageKey, JSON.stringify({ currentJobId, endTime, projectId, startTime }));
      return;
    }

    window.localStorage.removeItem(storageKey);
  }, [currentJobId, endTime, processing, projectId, startTime, storageKey]);
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
