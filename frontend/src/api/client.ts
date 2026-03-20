/**
 * frontend/src/api/client.ts
 * ============================
 * Merkezi API istemcisi.
 * Tüm fetch() çağrıları buradan yapılır — component'lar içinde
 * dağınık hardcoded URL'ler yok.
 */

import { useAuthRuntimeStore } from '../auth/runtime';
import { getCachedToken, isTokenUsable, resolveTokenExpiration } from '../auth/session';
import { API_BASE, API_REQUEST_TIMEOUT_MS, API_RETRY_COUNT, CLERK_JWT_TEMPLATE } from '../config';
import { extractApiErrorPayload, mergeApiHeaders } from './client.helpers';
import { createAppError, isAppError, type AppErrorCode } from './errors';
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
    StartJobResponse,
    CacheStatusResponse,
    ManualJobPayload,
    ManualCutUploadResponse,
    ReburnPayload,
    BatchJobPayload,
    SharePrefillResponse,
    SocialAccount,
    SocialPlatform,
    PublishJob,
    AccountDeletionResponse,
    AuthWhoAmIResponse,
} from '../types';

// ─── Kimlik Doğrulama (Clerk Token Injection) ──────────────────────────────────
export let activeToken: string | null = null;
let refreshTokenPromise: Promise<string> | null = null;

export const setApiToken = (token: string | null) => {
    activeToken = token;
};

interface GetFreshTokenOptions {
    forceRefresh?: boolean;
}

// Clerk'ten dinamik olarak en güncel tokeni çekmek için yardımcı fonksiyon
export async function getFreshToken({ forceRefresh = false }: GetFreshTokenOptions = {}): Promise<string> {
    if (!forceRefresh) {
        const reusableToken = getReusableToken();
        if (reusableToken) {
            return reusableToken;
        }
    }

    if (refreshTokenPromise) {
        return refreshTokenPromise;
    }

    refreshTokenPromise = refreshActiveToken(forceRefresh).finally(() => {
        refreshTokenPromise = null;
    });

    return refreshTokenPromise;
}

// ─── Tip yardımcıları ────────────────────────────────────────────────────────
function withApiHeaders(token: string | null, headers?: HeadersInit): Record<string, string> {
    return mergeApiHeaders(token, headers);
}

function readOnlineStatus(): boolean {
    if (typeof navigator === 'undefined') {
        return true;
    }

    return navigator.onLine;
}

function hasUsableActiveToken(): boolean {
    return isTokenUsable(activeToken, resolveTokenExpiration(activeToken));
}

function shouldRetry(error: unknown, attempt: number): boolean {
    if (attempt >= API_RETRY_COUNT) {
        return false;
    }

    return isAppError(error)
        && error.retryable
        && ['network_timeout', 'server_unavailable'].includes(error.code);
}

function sleep(ms: number): Promise<void> {
    return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function withPromiseTimeout<T>(promise: Promise<T>, timeoutMs: number): Promise<T> {
    return new Promise<T>((resolve, reject) => {
        const timeoutId = window.setTimeout(() => {
            reject(createAppError(
                'network_timeout',
                'Sunucu zamaninda yanit vermedi. Lutfen tekrar deneyin.',
                { retryable: true },
            ));
        }, timeoutMs);

        promise
            .then((value) => {
                window.clearTimeout(timeoutId);
                resolve(value);
            })
            .catch((error) => {
                window.clearTimeout(timeoutId);
                reject(error);
            });
    });
}

async function fetchWithTimeout(input: RequestInfo | URL, init: RequestInit): Promise<Response> {
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), API_REQUEST_TIMEOUT_MS);

    try {
        return await fetch(input, { ...init, signal: controller.signal });
    } catch (error) {
        if (error instanceof DOMException && error.name === 'AbortError') {
            throw createAppError(
                'network_timeout',
                'Sunucu zamaninda yanit vermedi. Lutfen internet baglantinizi kontrol edip tekrar deneyin.',
                { cause: error, retryable: true },
            );
        }

        if (!readOnlineStatus()) {
            throw createAppError(
                'network_offline',
                'Internet baglantinizi kontrol edin. Sunucuya su anda ulasilamiyor.',
                { cause: error, retryable: true },
            );
        }

        throw createAppError(
            'server_unavailable',
            'Sunucuya baglanirken hata olustu. Lutfen biraz sonra tekrar deneyin.',
            { cause: error, retryable: true },
        );
    } finally {
        window.clearTimeout(timeoutId);
    }
}

function classifyTokenError(error: unknown) {
    if (isAppError(error)) {
        return error;
    }

    if (!readOnlineStatus() && !hasUsableActiveToken()) {
        return createAppError(
            'auth_revalidation_required',
            'Internet baglantisi olmadigi icin oturum yeniden dogrulanamiyor. Baglanti geri geldiginde tekrar deneyin.',
            { cause: error, retryable: false, source: 'auth' },
        );
    }

    return createAppError(
        'auth_provider_unavailable',
        'Clerk oturum bilgisi alinamadi. Lutfen internet baglantinizi kontrol edip tekrar deneyin.',
        { cause: error, retryable: false, source: 'auth' },
    );
}

function getProtectedTokenExpiry(token: string | null = activeToken): number | null {
    return resolveTokenExpiration(token);
}

function syncProtectedRequests(token: string | null): void {
    useAuthRuntimeStore.getState().setProtectedRequestsFresh(token);
}

function pauseProtectedRequests(
    reason: AppErrorCode,
    token: string | null = activeToken,
): void {
    useAuthRuntimeStore.getState().pauseProtectedRequests(reason, getProtectedTokenExpiry(token));
}

function getReusableToken(): string | null {
    if (hasUsableActiveToken()) {
        syncProtectedRequests(activeToken);
        return activeToken;
    }

    const cachedToken = getCachedToken();
    if (cachedToken) {
        activeToken = cachedToken;
        syncProtectedRequests(cachedToken);
        return cachedToken;
    }

    return null;
}

function buildRequestInit(init: RequestInit | undefined, token: string): RequestInit {
    return {
        ...init,
        headers: withApiHeaders(token, init?.headers),
    };
}

async function refreshActiveToken(forceRefresh: boolean): Promise<string> {
    const cachedToken = getCachedToken();
    const tokenExpiresAt = getProtectedTokenExpiry(activeToken) ?? getProtectedTokenExpiry(cachedToken);

    if (!readOnlineStatus()) {
        if (!forceRefresh) {
            const offlineToken = getReusableToken();
            if (offlineToken) {
                return offlineToken;
            }
        }

        pauseProtectedRequests('network_offline', cachedToken ?? activeToken);
        throw createAppError(
            'auth_revalidation_required',
            'Internet baglantisi olmadigi icin oturum yeniden dogrulanamiyor. Baglanti geri geldiginde tekrar deneyin.',
            { source: 'auth' },
        );
    }

    const clerkSession = typeof window !== 'undefined' ? window.Clerk?.session : null;
    if (!clerkSession) {
        if (!forceRefresh) {
            const fallbackToken = getReusableToken();
            if (fallbackToken) {
                return fallbackToken;
            }
        }

        pauseProtectedRequests('unauthorized', cachedToken ?? activeToken);
        throw createAppError(
            'unauthorized',
            'Oturum dogrulanamadi. Lutfen yeniden giris yapin.',
            { source: 'auth' },
        );
    }

    useAuthRuntimeStore.getState().setProtectedRequestsRefreshing(tokenExpiresAt);

    try {
        const token = await withPromiseTimeout(
            CLERK_JWT_TEMPLATE
                ? clerkSession.getToken({ template: CLERK_JWT_TEMPLATE })
                : clerkSession.getToken(),
            API_REQUEST_TIMEOUT_MS,
        );

        if (!token) {
            throw createAppError(
                'auth_provider_unavailable',
                'Clerk oturum bilgisi alinamadi. Lutfen internet baglantinizi kontrol edip tekrar deneyin.',
                { source: 'auth' },
            );
        }

        activeToken = token;
        syncProtectedRequests(token);
        return token;
    } catch (error) {
        if (!forceRefresh) {
            const fallbackToken = getReusableToken();
            if (fallbackToken) {
                return fallbackToken;
            }
        }

        const classified = classifyTokenError(error);
        pauseProtectedRequests(classified.code, cachedToken ?? activeToken);
        throw classified;
    }
}

function createResponseError(
    code: Parameters<typeof createAppError>[0],
    message: string,
    response: Response,
    detailCode?: string,
    retryable = false,
) {
    return createAppError(code, message, {
        detailCode,
        retryable,
        source: 'api',
        status: response.status,
    });
}

function classifyUnauthorizedResponse(response: Response, code: string | null) {
    if (code === 'interactive_static_token_disabled') {
        return createResponseError(
            'unauthorized',
            'Tarayici oturumlari Clerk ile dogrulanmali. Static token bu akista desteklenmiyor.',
            response,
            code,
        );
    }

    if (code === 'token_expired') {
        return createResponseError('token_expired', 'Oturumunuzun suresi doldu. Lutfen yeniden giris yapin.', response, code);
    }

    if (response.status === 401) {
        return createResponseError('unauthorized', 'Oturum dogrulanamadi. Lutfen yeniden giris yapin.', response, code ?? 'unauthorized');
    }

    return createResponseError('forbidden', 'Bu islem icin yetkiniz yok.', response, code ?? 'forbidden');
}

function classifyServerResponse(response: Response, code: string | null, message: string) {
    if (response.status === 503 || code === 'auth_provider_unavailable') {
        return createResponseError(
            'auth_provider_unavailable',
            'Kimlik dogrulama servisi gecici olarak erisilemiyor. Lutfen biraz sonra tekrar deneyin.',
            response,
            code ?? 'auth_provider_unavailable',
            true,
        );
    }

    if ([408, 429, 502, 504].includes(response.status)) {
        return createResponseError('network_timeout', 'Sunucu zamaninda yanit vermedi. Lutfen tekrar deneyin.', response, code ?? undefined, true);
    }

    return createResponseError(
        'server_unavailable',
        message || 'Sunucu gecici olarak erisilemiyor. Lutfen biraz sonra tekrar deneyin.',
        response,
        code ?? undefined,
        true,
    );
}

function classifyApiResponseError(path: string, response: Response, text: string) {
    const { code, message } = extractApiErrorPayload(text, response.status);

    if (response.status === 401 || response.status === 403) {
        return classifyUnauthorizedResponse(response, code);
    }

    if (response.status === 404) {
        return createResponseError(
            'unknown',
            'Istenen kaynak su anda kullanilamiyor.',
            response,
            code ?? 'not_found',
        );
    }

    if (response.status === 422) {
        return createResponseError('validation_error', message || 'Gonderilen veri gecersiz.', response, code ?? undefined);
    }

    if (response.status >= 500) {
        return classifyServerResponse(response, code, message);
    }

    return createResponseError('unknown', message || `API ${path} hatasi`, response, code ?? undefined);
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
    let attempt = 0;
    let canReplayAuth = true;

    while (true) {
        try {
            const token = await getFreshToken();
            const response = await fetchWithTimeout(`${API_BASE}${path}`, buildRequestInit(init, token));
            if (!response.ok) {
                const text = await response.text();
                const error = classifyApiResponseError(path, response, text);

                if (canReplayAuth && isAppError(error) && error.code === 'token_expired') {
                    canReplayAuth = false;
                    const replayToken = await getFreshToken({ forceRefresh: true });
                    const replayResponse = await fetchWithTimeout(`${API_BASE}${path}`, buildRequestInit(init, replayToken));

                    if (!replayResponse.ok) {
                        const replayText = await replayResponse.text();
                        const replayError = classifyApiResponseError(path, replayResponse, replayText);
                        if (isAppError(replayError) && ['token_expired', 'unauthorized'].includes(replayError.code)) {
                            pauseProtectedRequests('token_expired');
                        }
                        throw replayError;
                    }

                    return replayResponse.json() as Promise<T>;
                }

                if (isAppError(error) && ['token_expired', 'unauthorized'].includes(error.code)) {
                    pauseProtectedRequests(error.code === 'token_expired' ? 'token_expired' : 'unauthorized');
                }

                throw error;
            }

            return response.json() as Promise<T>;
        } catch (error) {
            if (!shouldRetry(error, attempt)) {
                throw error;
            }

            attempt += 1;
            await sleep(Math.min(1000 * attempt, 3000));
        }
    }
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
    return requestJson<T>(path, {
        headers: { 'Content-Type': 'application/json', ...(init?.headers as Record<string, string> | undefined) },
        ...init,
    });
}

export const authApi = {
    whoami: () =>
        apiFetch<AuthWhoAmIResponse>('/api/auth/whoami'),
};

// ─── Job endpoint'leri ────────────────────────────────────────────────────────

export const jobsApi = {
    /** Tüm aktif ve bekleyen işleri getir */
    list: () =>
        apiFetch<{ jobs: Job[] }>('/api/jobs'),

    /** Girilen ayarlar için cache durumunu önceden kontrol et */
    cacheStatus: (payload: StartJobPayload) =>
        apiFetch<CacheStatusResponse>(
            '/api/cache-status',
            { method: 'POST', body: JSON.stringify(payload) },
        ),

    /** Yeni bir iş başlat */
    start: (payload: StartJobPayload) =>
        apiFetch<StartJobResponse>(
            '/api/start-job',
            { method: 'POST', body: JSON.stringify(payload) },
        ),

    /** Bir işi iptal et */
    cancel: (jobId: string) =>
        apiFetch<{ status: string; message: string }>(`/api/cancel-job/${jobId}`, { method: 'POST' }),

    /** Kullanılabilir stilleri getir */
    styles: () =>
        apiFetch<{ styles: string[]; animations: Array<{ value: string; label: string }> }>('/api/styles'),
};

// ─── Klip endpoint'leri ───────────────────────────────────────────────────────

export const clipsApi = {
    /** Üretilen klipleri listele */
    list: (page = 1, pageSize = 50) =>
        apiFetch<ClipListResponse>(`/api/clips?page=${page}&page_size=${pageSize}`),

    /** Bir klibin transkriptini getir */
    getTranscript: (clipName: string, project_id: string) =>
        apiFetch<ClipTranscriptResponse>(
            `/api/clip-transcript/${clipName}?project_id=${encodeURIComponent(project_id)}`
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
        return requestJson<{ status: string; job_id: string; project_id?: string; message?: string }>('/api/upload', {
            method: 'POST',
            body: form,
        });
    },
};

// ─── Editör endpoint'leri ─────────────────────────────────────────────────────

export const editorApi = {
    /** Proje listesini getir. Hata durumunda error ile döner. */
    getProjects: async (): Promise<{
        projects: ProjectSummary[];
        error?: string;
    }> => {
        try {
            return await apiFetch<{ projects: ProjectSummary[] }>('/api/projects');
        } catch (err) {
            return { projects: [], error: err instanceof Error ? err.message : 'Projeler alınamadı' };
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
            animation_type?: string;
            skip_subtitles?: boolean;
            num_clips?: number;
            cut_points?: number[];
            cut_as_short?: boolean;
            layout?: 'auto' | 'single' | 'split';
            duration_min?: number;
            duration_max?: number;
        },
    ): Promise<ManualCutUploadResponse> => {
        const form = new FormData();
        form.append('file', file);
        form.append('start_time', String(payload.start_time));
        form.append('end_time', String(payload.end_time));
        form.append('style_name', payload.style_name ?? 'HORMOZI');
        form.append('animation_type', payload.animation_type ?? 'default');
        form.append('skip_subtitles', String(payload.skip_subtitles ?? false));
        form.append('num_clips', String(payload.num_clips ?? 1));
        form.append('cut_as_short', String(payload.cut_as_short ?? true));
        form.append('layout', payload.layout ?? 'auto');
        if (typeof payload.duration_min === 'number') {
            form.append('duration_min', String(payload.duration_min));
        }
        if (typeof payload.duration_max === 'number') {
            form.append('duration_max', String(payload.duration_max));
        }
        if (payload.cut_points && payload.cut_points.length >= 2) {
            form.append('cut_points', JSON.stringify(payload.cut_points));
        }

        return requestJson<ManualCutUploadResponse>('/api/manual-cut-upload', {
            method: 'POST',
            body: form,
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

export const accountApi = {
    deleteMyData: (confirm = 'DELETE') =>
        apiFetch<AccountDeletionResponse>('/api/account/me/data', {
            method: 'DELETE',
            body: JSON.stringify({ confirm }),
        }),
};
