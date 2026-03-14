/**
 * frontend/src/api/client.ts
 * ============================
 * Merkezi API istemcisi.
 * Tüm fetch() çağrıları buradan yapılır — component'lar içinde
 * dağınık hardcoded URL'ler yok.
 */

import { API_BASE, CLERK_JWT_TEMPLATE } from '../config';
import { extractApiErrorMessage, mergeApiHeaders } from './client.helpers';
import type {
    Job,
    ClipListResponse,
    DeleteClipResponse,
    Segment,
    ClipMetadata,
    ClipTranscriptResponse,
    ClipTranscriptRecoveryPayload,
    ProjectSummary,
    ProjectTranscriptResponse,
    ProjectTranscriptRecoveryPayload,
    StartJobPayload,
    ManualJobPayload,
    ManualCutUploadResponse,
    ReburnPayload,
    BatchJobPayload,
    SharePrefillResponse,
    SocialAccount,
    SocialPlatform,
    PublishJob,
} from '../types';

// ─── Kimlik Doğrulama (Clerk Token Injection) ──────────────────────────────────
export let activeToken: string | null = null;

export const setApiToken = (token: string | null) => {
    activeToken = token;
};

// Clerk'ten dinamik olarak en güncel tokeni çekmek için yardımcı fonksiyon
export async function getFreshToken(): Promise<string | null> {
    if (typeof window !== "undefined" && window.Clerk?.session) {
        const token = CLERK_JWT_TEMPLATE
            ? await window.Clerk.session.getToken({ template: CLERK_JWT_TEMPLATE })
            : await window.Clerk.session.getToken();
        activeToken = token;
        return token;
    }
    return activeToken;
}

// ─── Tip yardımcıları ────────────────────────────────────────────────────────
function withApiHeaders(headers?: HeadersInit): Record<string, string> {
    return mergeApiHeaders(activeToken, headers);
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
    await getFreshToken();
    const response = await fetch(`${API_BASE}${path}`, {
        headers: { 'Content-Type': 'application/json', ...withApiHeaders(init?.headers) },
        ...init,
    });
    if (!response.ok) {
        const text = await response.text();
        const msg = extractApiErrorMessage(text, response.status);
        throw new Error(`API ${path} → ${response.status}: ${msg}`);
    }
    return response.json() as Promise<T>;
}

// ─── Job endpoint'leri ────────────────────────────────────────────────────────

export const jobsApi = {
    /** Tüm aktif ve bekleyen işleri getir */
    list: () =>
        apiFetch<{ jobs: Job[] }>('/api/jobs'),

    /** Yeni bir iş başlat */
    start: (payload: StartJobPayload) =>
        apiFetch<{ status: string; job_id: string; message: string; gpu_locked: boolean }>(
            '/api/start-job',
            { method: 'POST', body: JSON.stringify(payload) },
        ),

    /** Bir işi iptal et */
    cancel: (jobId: string) =>
        apiFetch<{ status: string; message: string }>(`/api/cancel-job/${jobId}`, { method: 'POST' }),

    /** Kullanılabilir stilleri getir */
    styles: () =>
        apiFetch<{ styles: string[] }>('/api/styles'),
};

// ─── Klip endpoint'leri ───────────────────────────────────────────────────────

export const clipsApi = {
    /** Üretilen klipleri listele */
    list: (page = 1, pageSize = 50) =>
        apiFetch<ClipListResponse>(`/api/clips?page=${page}&page_size=${pageSize}`),

    /** Bir klibin transkriptini getir */
    getTranscript: (clipName: string, project_id?: string) =>
        apiFetch<ClipTranscriptResponse>(
            `/api/clip-transcript/${clipName}${project_id ? `?project_id=${project_id}` : ''}`
        ),

    /** Bir klibi ve ilişkili shorts varlıklarını sil */
    delete: (projectId: string, clipName: string) =>
        apiFetch<DeleteClipResponse>(
            `/api/projects/${encodeURIComponent(projectId)}/shorts/${encodeURIComponent(clipName)}`,
            { method: 'DELETE' },
        ),

    /** Yerel video yükle */
    upload: (file: File): Promise<{ status: string; job_id: string; project_id?: string; message?: string }> => {
        const form = new FormData();
        form.append('file', file);
        return getFreshToken().then(() => fetch(`${API_BASE}/api/upload`, { method: 'POST', headers: withApiHeaders(), body: form }))
            .then(async (response) => {
                if (!response.ok) {
                    const text = await response.text();
                    throw new Error(`Upload failed: ${response.status} - ${text}`);
                }
                return response.json();
            });
    },
};

// ─── Editör endpoint'leri ─────────────────────────────────────────────────────

export const editorApi = {
    /** Proje listesini getir. 404 ise clips'tan project ID'leri türetir. Hata durumunda error ile döner. */
    getProjects: async (): Promise<{
        projects: ProjectSummary[];
        error?: string;
    }> => {
        try {
            return await apiFetch<{ projects: ProjectSummary[] }>('/api/projects');
        } catch (err) {
            const apiError = err instanceof Error ? err.message : 'Projeler alınamadı';
            try {
                const { clips } = await apiFetch<{ clips: { project?: string }[] }>('/api/clips');
                const ids = [...new Set((clips ?? []).map((c) => c.project).filter((p): p is string => Boolean(p) && p !== 'legacy'))];
                return {
                    projects: ids.map((id) => ({
                        active_job_id: null,
                        has_master: true,
                        has_transcript: true,
                        id,
                        last_error: null,
                        transcript_status: 'ready',
                    })),
                    error: apiError,
                };
            } catch {
                return { projects: [], error: apiError };
            }
        }
    },

    /** Mevcut ana transkripti getir */
    getTranscript: (project_id?: string) =>
        apiFetch<ProjectTranscriptResponse | { transcript: Segment[] | ClipMetadata }>(
            `/api/transcript${project_id ? `?project_id=${project_id}` : ''}`
        ),

    /** Ana transkripti kaydet */
    saveTranscript: (transcript: Segment[], project_id?: string) =>
        apiFetch<{ status: string }>(
            `/api/transcript${project_id ? `?project_id=${project_id}` : ''}`,
            {
                method: 'POST',
                body: JSON.stringify(transcript),
            }
        ),

    recoverProjectTranscript: (payload: ProjectTranscriptRecoveryPayload) =>
        apiFetch<{ status: string; job_id?: string | null }>('/api/transcript/recover', {
            method: 'POST',
            body: JSON.stringify(payload),
        }),

    /** Manuel klip oluştur */
    processManual: (payload: ManualJobPayload) =>
        apiFetch<{ status: string; job_id: string }>('/api/process-manual', {
            method: 'POST',
            body: JSON.stringify(payload),
        }),

    /** Klibin altyazılarını yeniden yaz */
    reburn: (payload: ReburnPayload) =>
        apiFetch<{ status: string; job_id: string }>('/api/reburn', {
            method: 'POST',
            body: JSON.stringify(payload),
        }),

    /** Mevcut klip metadata/transkriptini akıllı fallback ile kurtar */
    recoverClipTranscript: (payload: ClipTranscriptRecoveryPayload) =>
        apiFetch<{ status: string; job_id?: string | null }>('/api/clip-transcript/recover', {
            method: 'POST',
            body: JSON.stringify(payload),
        }),

    /** Seçilen aralıkta AI ile toplu klip üretir */
    processBatch: (payload: BatchJobPayload) =>
        apiFetch<{ status: string; job_id: string }>('/api/process-batch', {
            method: 'POST',
            body: JSON.stringify(payload),
        }),

    /** Tek adımda video upload + transcript + auto-cut render */
    manualCutUpload: (
        file: File,
        payload: {
            start_time: number;
            end_time: number;
            style_name?: string;
            skip_subtitles?: boolean;
            num_clips?: number;
            cut_points?: number[];
            cut_as_short?: boolean;
        },
    ): Promise<ManualCutUploadResponse> => {
        const form = new FormData();
        form.append('file', file);
        form.append('start_time', String(payload.start_time));
        form.append('end_time', String(payload.end_time));
        form.append('style_name', payload.style_name ?? 'HORMOZI');
        form.append('skip_subtitles', String(payload.skip_subtitles ?? false));
        form.append('num_clips', String(payload.num_clips ?? 1));
        form.append('cut_as_short', String(payload.cut_as_short ?? true));
        if (payload.cut_points && payload.cut_points.length >= 2) {
            form.append('cut_points', JSON.stringify(payload.cut_points));
        }

        return getFreshToken().then(() => fetch(`${API_BASE}/api/manual-cut-upload`, { method: 'POST', headers: withApiHeaders(), body: form }))
            .then(async (response) => {
                if (!response.ok) {
                    const text = await response.text();
                    throw new Error(`Manual cut failed: ${response.status} - ${text}`);
                }
                return response.json();
            });
    },
};

// ─── Social publish endpoint'leri ─────────────────────────────────────────────

export const socialApi = {
    saveCredentials: (payload: { provider: 'postiz'; api_key: string }) =>
        apiFetch<{ status: string; provider: string; accounts: SocialAccount[] }>('/api/social/credentials', {
            method: 'POST',
            body: JSON.stringify(payload),
        }),

    deleteCredentials: () =>
        apiFetch<{ status: string; provider: string }>('/api/social/credentials?provider=postiz', {
            method: 'DELETE',
        }),

    getAccounts: () =>
        apiFetch<{ connected: boolean; provider: string; workspace_id?: string; accounts: SocialAccount[] }>('/api/social/accounts'),

    getPrefill: (project_id: string, clip_name: string) =>
        apiFetch<SharePrefillResponse>(`/api/social/prefill?project_id=${encodeURIComponent(project_id)}&clip_name=${encodeURIComponent(clip_name)}`),

    saveDrafts: (
        project_id: string,
        clip_name: string,
        platforms: Partial<Record<SocialPlatform, { title: string; text: string; hashtags: string[]; hook_text?: string; viral_score?: number }>>,
    ) =>
        apiFetch<{ status: string }>('/api/social/drafts', {
            method: 'PUT',
            body: JSON.stringify({ project_id, clip_name, platforms }),
        }),

    deleteDrafts: (project_id: string, clip_name: string) =>
        apiFetch<{ status: string; deleted: number }>(
            `/api/social/drafts?project_id=${encodeURIComponent(project_id)}&clip_name=${encodeURIComponent(clip_name)}`,
            {
                method: 'DELETE',
            }
        ),

    publish: (payload: {
        project_id: string;
        clip_name: string;
        mode: 'now' | 'scheduled';
        scheduled_at?: string;
        timezone?: string;
        approval_required?: boolean;
        targets: { account_id: string; platform: SocialPlatform; provider?: string }[];
        content_by_platform: Partial<Record<SocialPlatform, { title: string; text: string; hashtags: string[]; hook_text?: string; viral_score?: number }>>;
    }) =>
        apiFetch<{ status: string; jobs: Array<{ id: string; platform: SocialPlatform; account_id: string; state: string; scheduled_at?: string | null }>; errors?: Array<{ job_id: string; error: string }> }>('/api/social/publish', {
            method: 'POST',
            body: JSON.stringify(payload),
        }),

    getPublishJobs: (project_id?: string, clip_name?: string) =>
        apiFetch<{ jobs: PublishJob[] }>(
            `/api/social/publish-jobs${project_id || clip_name
                ? `?${[
                    project_id ? `project_id=${encodeURIComponent(project_id)}` : '',
                    clip_name ? `clip_name=${encodeURIComponent(clip_name)}` : '',
                ].filter(Boolean).join('&')}`
                : ''}`
        ),

    approveJob: (job_id: string) =>
        apiFetch<{ status: string; job_id: string }>(`/api/social/publish-jobs/${encodeURIComponent(job_id)}/approve`, {
            method: 'POST',
        }),

    cancelJob: (job_id: string) =>
        apiFetch<{ status: string; job_id: string }>(`/api/social/publish-jobs/${encodeURIComponent(job_id)}/cancel`, {
            method: 'POST',
        }),
};
