import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { Select } from '../../../components/ui/Select';

const options = [
  { value: 'cloud', label: 'Cloud' },
  { value: 'local', label: 'Local' },
];

describe('Select', () => {
  it('renders its label and placeholder', () => {
    render(
      <Select
        id="engine"
        label="AI Core Engine"
        options={options}
        value=""
        onChange={vi.fn()}
        placeholder="Choose one"
      />,
    );

    expect(screen.getByLabelText(/ai core engine/i)).toBeInTheDocument();
    expect(screen.getByText('Choose one')).toBeInTheDocument();
  });

  it('opens the listbox and emits changes', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();

    render(<Select options={options} value="" onChange={onChange} />);

    await user.click(screen.getByRole('button'));
    expect(screen.getByRole('listbox')).toBeInTheDocument();

    await user.click(screen.getByRole('option', { name: 'Local' }));
    expect(onChange).toHaveBeenCalledWith('local');
    await waitFor(() => {
      expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
    });
  });

  it('closes when escape or outside click happens', async () => {
    const user = userEvent.setup();

    render(<Select options={options} value="cloud" onChange={vi.fn()} />);

    await user.click(screen.getByRole('button'));
    expect(screen.getByRole('listbox')).toBeInTheDocument();

    fireEvent.keyDown(window, { key: 'Escape' });
    await waitFor(() => {
      expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
    });

    await user.click(screen.getByRole('button'));
    fireEvent.mouseDown(document.body);
    await waitFor(() => {
      expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
    });
  });
});
