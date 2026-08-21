import { apiFetch } from './client';
import type { PreviewAnalyzeResponse } from '../types/preview';

export const previewApi = {
  analyze: (url: string) => apiFetch<PreviewAnalyzeResponse>('/api/preview/analyze', {
    method: 'POST',
    body: JSON.stringify({ url }),
  }),
};
