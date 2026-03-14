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

export function extractApiErrorMessage(text: string, status: number): string {
  const detail = parseApiErrorDetail(text);

  if (typeof detail === 'string') {
    return detail;
  }

  const nestedMessage = readNestedErrorMessage(detail);
  if (nestedMessage) {
    return nestedMessage;
  }

  if (Array.isArray(detail)) {
    return detail.map((entry) => readArrayErrorMessage(entry)).join('; ');
  }

  return text || `HTTP ${status}`;
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

function readNestedErrorMessage(detail: unknown): string | null {
  if (!detail || typeof detail !== 'object' || !('error' in detail)) {
    return null;
  }

  const errorValue = (detail as { error?: { message?: string } }).error;
  return errorValue?.message ?? null;
}

function readArrayErrorMessage(entry: unknown): string {
  return typeof entry === 'object' && entry && 'msg' in entry
    ? ((entry as { msg?: string }).msg ?? String(entry))
    : String(entry);
}
