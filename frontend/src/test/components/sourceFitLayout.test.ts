import { beforeEach, expect, it } from 'vitest';
import { getLayoutSelectOptions, readInitialLayout } from '../../components/jobForm/helpers';
import { resolvePreviewLayout } from '../../config/subtitleStyles';

beforeEach(() => window.localStorage.clear());
it('offers fit explicitly, preserves the preference and leaves the default auto', () => {
  expect(getLayoutSelectOptions().some(option => option.value === 'fit')).toBe(true);
  expect(readInitialLayout()).toBe('auto');
  window.localStorage.setItem('godtier-job-form-preferences', JSON.stringify({ layout: 'fit' }));
  expect(readInitialLayout()).toBe('fit');
  expect(resolvePreviewLayout('fit')).toBe('fit');
});
