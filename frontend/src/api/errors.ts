export type AppErrorCode =
  | 'network_offline'
  | 'network_timeout'
  | 'auth_provider_unavailable'
  | 'auth_revalidation_required'
  | 'token_expired'
  | 'unauthorized'
  | 'forbidden'
  | 'server_unavailable'
  | 'validation_error'
  | 'unknown';

export interface AppErrorOptions {
  cause?: unknown;
  detailCode?: string;
  retryable?: boolean;
  source?: 'api' | 'auth' | 'ws';
  status?: number;
}

export class AppError extends Error {
  cause?: unknown;
  code: AppErrorCode;
  detailCode?: string;
  retryable: boolean;
  source: 'api' | 'auth' | 'ws';
  status?: number;

  constructor(code: AppErrorCode, message: string, options: AppErrorOptions = {}) {
    super(message);
    this.name = 'AppError';
    this.code = code;
    this.cause = options.cause;
    this.detailCode = options.detailCode;
    this.retryable = options.retryable ?? false;
    this.source = options.source ?? 'api';
    this.status = options.status;
  }
}

export function createAppError(
  code: AppErrorCode,
  message: string,
  options?: AppErrorOptions,
): AppError {
  return new AppError(code, message, options);
}

export function isAppError(error: unknown): error is AppError {
  return error instanceof AppError;
}

export function getAppErrorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}
