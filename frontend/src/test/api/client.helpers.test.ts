import { describe, expect, it } from 'vitest';

import { extractApiErrorMessage, extractApiErrorPayload, mergeApiHeaders } from '../../api/client.helpers';

describe('client helpers', () => {
  it('merges bearer auth into plain header objects', () => {
    expect(mergeApiHeaders('token-123', { 'X-Test': '1' })).toEqual({
      Authorization: 'Bearer token-123',
      'X-Test': '1',
    });
  });

  it('extracts string and nested object API errors', () => {
    expect(extractApiErrorMessage(JSON.stringify({ detail: 'Forbidden' }), 403)).toBe('Forbidden');
    expect(
      extractApiErrorPayload(
        JSON.stringify({ detail: { error: { code: 'auth_provider_unavailable', message: 'Provider unavailable' } } }),
        503,
      ),
    ).toEqual({
      code: 'auth_provider_unavailable',
      message: 'Provider unavailable',
    });
    expect(
      extractApiErrorMessage(
        JSON.stringify({ detail: { error: { message: 'Provider unavailable' } } }),
        502,
      ),
    ).toBe('Provider unavailable');
  });

  it('formats validation arrays and falls back to raw text', () => {
    expect(
      extractApiErrorMessage(
        JSON.stringify({ detail: [{ msg: 'field required' }, { msg: 'invalid url' }] }),
        422,
      ),
    ).toBe('field required; invalid url');

    expect(extractApiErrorMessage('gateway timeout', 504)).toBe('gateway timeout');
    expect(extractApiErrorMessage('', 500)).toBe('HTTP 500');
  });
});
