import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { renderJobForm } from './jobForm.test-helpers';

describe('JobForm accessibility and layout', () => {
  it('has labels linked to inputs via htmlFor', async () => {
    await renderJobForm();

    const urlInput = screen.getByLabelText(/source feed url/i);
    expect(urlInput).toBeInTheDocument();
    expect(urlInput.tagName).toBe('INPUT');

    const styleSelect = screen.getByLabelText(/visual style/i);
    expect(styleSelect).toBeInTheDocument();
    expect(styleSelect.tagName).toBe('BUTTON');

    const motionSelect = screen.getByLabelText(/motion style/i);
    expect(motionSelect).toBeInTheDocument();
    expect(motionSelect.tagName).toBe('BUTTON');

    const engineSelect = screen.getByLabelText(/ai core engine/i);
    expect(engineSelect).toBeInTheDocument();
  });

  it('renders responsive layout classes and toggles', async () => {
    const { container } = await renderJobForm();

    const sourceGrid = container.querySelector('.grid.grid-cols-1.md\\:grid-cols-4');
    expect(sourceGrid?.className).toContain('grid-cols-1');
    expect(sourceGrid?.className).toContain('md:grid-cols-4');

    const controlGrid = screen.getByTestId('job-form-control-grid');
    expect(controlGrid.className).toContain('grid-cols-1');
    expect(controlGrid.className).toContain('lg:grid-cols-2');

    expect(screen.getByRole('switch', { name: /altyaz/i })).toHaveAttribute('aria-checked', 'false');
    expect(screen.getByLabelText(/target clone count/i)).toBeInTheDocument();
    expect(screen.getByRole('switch', { name: /otomatik mod/i })).toBeInTheDocument();
  });

  it('keeps select triggers clipped inside narrow control cards', async () => {
    await renderJobForm();

    const styleSelect = screen.getByLabelText(/visual style/i);
    const engineSelect = screen.getByLabelText(/ai core engine/i);

    expect(styleSelect.className).toContain('overflow-hidden');
    expect(styleSelect.className).toContain('min-w-0');
    expect(engineSelect.className).toContain('overflow-hidden');
    expect(engineSelect.className).toContain('min-w-0');
  });

  it('hides manual duration inputs while auto mode is active', async () => {
    await renderJobForm();

    expect(screen.getByRole('switch', { name: /otomatik mod/i })).toHaveAttribute('aria-checked', 'true');
    expect(screen.queryByLabelText(/min sure/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/max sure/i)).not.toBeInTheDocument();
  });
});
