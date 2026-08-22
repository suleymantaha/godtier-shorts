import { beforeEach, describe, expect, it } from 'vitest';

import { readAppState, readQueryViewMode } from '../../app/helpers';
import { PENDING_PREVIEW_URL_KEY } from '../../marketing/funnel';

describe('preview funnel navigation', () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    window.history.replaceState({}, '', '/');
  });

  it('opens Viral Scan after signup when landing captured a URL', () => {
    sessionStorage.setItem(PENDING_PREVIEW_URL_KEY, 'https://youtu.be/abc123DEF45');

    expect(readAppState().viewMode).toBe('preview');
  });

  it('routes signed-in billing links to the billing account view', () => {
    expect(readQueryViewMode('?tab=billing')).toBe('billing');
  });
});
