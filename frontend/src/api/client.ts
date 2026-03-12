/**
 * frontend/src/api/client.ts
 * ============================
 * Merkezi API istemcisi.
 * Tüm fetch() çağrıları buradan yapılır — component'lar içinde
 * dağınık hardcoded URL'ler yok.
 */

import { API_BASE, CLERK_JWT_TEMPLATE } from '../config';
import type {
    Job,
    ClipListResponse,
    Segment,
    ClipMetadata,
    StartJobPayload,
    ManualJobPayload,
    ManualCutUploadResponse,
    ReburnPayload,
    BatchJobPayload,
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
    const result: Record<string, string> = {};
    if (activeToken) result.Authorization = `Bearer ${activeToken}`;
    if (headers && typeof headers === 'object' && !Array.isArray(headers) && !(headers instanceof Headers)) {
        Object.assign(result, headers as Record<string, string>);
    }
    return result;
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
    await getFreshToken();
    const response = await fetch(`${API_BASE}${path}`, {
        headers: { 'Content-Type': 'application/json', ...withApiHeaders(init?.headers) },
        ...init,
    });
    if (!response.ok) {
        const text = await response.text();
        let body: { detail?: unknown } | null = null;
        try {
            body = text ? (JSON.parse(text) as { detail?: unknown }) : null;
        } catch {
            /* non-JSON body */
        }
        const detail = body?.detail;
        const detailError =
            detail && typeof detail === 'object' && 'error' in (detail as Record<string, unknown>)
                ? (detail as { error?: { message?: string } }).error
                : null;
        const msg =
            typeof detail === 'string'
                ? detail
                : detailError?.message
                    ? detailError.message
                : Array.isArray(detail)
                    ? detail.map((e: { msg?: string }) => e?.msg ?? String(e)).join('; ')
                    : text || `HTTP ${response.status}`;
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
        apiFetch<{ transcript: Segment[] | ClipMetadata }>(
            `/api/clip-transcript/${clipName}${project_id ? `?project_id=${project_id}` : ''}`
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
        projects: { id: string; has_master: boolean; has_transcript: boolean }[];
        error?: string;
    }> => {
        try {
            return await apiFetch<{ projects: { id: string; has_master: boolean; has_transcript: boolean }[] }>('/api/projects');
        } catch (err) {
            const apiError = err instanceof Error ? err.message : 'Projeler alınamadı';
            try {
                const { clips } = await apiFetch<{ clips: { project?: string }[] }>('/api/clips');
                const ids = [...new Set((clips ?? []).map((c) => c.project).filter((p): p is string => Boolean(p) && p !== 'legacy'))];
                return { projects: ids.map((id) => ({ id, has_master: true, has_transcript: true })), error: apiError };
            } catch {
                return { projects: [], error: apiError };
            }
        }
    },

    /** Mevcut ana transkripti getir */
    getTranscript: (project_id?: string) =>
        apiFetch<{ transcript: Segment[] | ClipMetadata }>(
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
