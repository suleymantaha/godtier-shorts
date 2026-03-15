export function mergeApiHeaders(
  token: string | null,
  headers?: HeadersInit,
): Record<string, string> {
  const result: Record<string, string> = {};

  if (token) {
    result.Authorization = `Bearer ${token}`;
  }

  if (headers && typeof headers === 'object' && !Array.isArray(headers) && !(headers instanceof Headers)) {
    Object.assign(result, headers as Record<string, string>);
  }

  return result;
}

export interface ParsedApiError {
  code: string | null;
  message: string;
}

export function extractApiErrorPayload(text: string, status: number): ParsedApiError {
  const detail = parseApiErrorDetail(text);

  if (typeof detail === 'string') {
    return {
      code: null,
      message: detail,
    };
  }

  const nestedError = readNestedError(detail);
  if (nestedError) {
    return nestedError;
  }

  if (Array.isArray(detail)) {
    return {
      code: null,
      message: detail.map((entry) => readArrayErrorMessage(entry)).join('; '),
    };
  }

  return {
    code: null,
    message: text || `HTTP ${status}`,
  };
}

export function extractApiErrorMessage(text: string, status: number): string {
  return extractApiErrorPayload(text, status).message;
}

function parseApiErrorDetail(text: string): unknown {
  if (!text) {
    return null;
  }

  try {
    return (JSON.parse(text) as { detail?: unknown }).detail ?? null;
  } catch {
    return null;
  }
}

function readNestedError(detail: unknown): ParsedApiError | null {
  if (!detail || typeof detail !== 'object' || !('error' in detail)) {
    return null;
  }

  const errorValue = (detail as { error?: { code?: string; message?: string } }).error;
  if (!errorValue?.message) {
    return null;
  }

  return {
    code: errorValue.code ?? null,
    message: errorValue.message,
  };
}

function readArrayErrorMessage(entry: unknown): string {
  return typeof entry === 'object' && entry && 'msg' in entry
    ? ((entry as { msg?: string }).msg ?? String(entry))
    : String(entry);
}
