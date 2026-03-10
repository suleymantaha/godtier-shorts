import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { RangeSlider } from '../../components/RangeSlider';

describe('RangeSlider', () => {
  const defaultProps = {
    min: 0,
    max: 100,
    start: 10,
    end: 80,
    onChange: vi.fn(),
  };

  it('renders two range inputs with accessible labels', () => {
    render(<RangeSlider {...defaultProps} />);
    expect(screen.getByLabelText(/start/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/end/i)).toBeInTheDocument();
  });

  it('sets correct min/max/value attributes', () => {
    render(<RangeSlider {...defaultProps} />);
    const startInput = screen.getByLabelText(/start/i) as HTMLInputElement;
    const endInput = screen.getByLabelText(/end/i) as HTMLInputElement;
    expect(startInput.value).toBe('10');
    expect(endInput.value).toBe('80');
    expect(startInput.min).toBe('0');
    expect(endInput.max).toBe('100');
  });

  it('calls onChange when start value changes', () => {
    const onChange = vi.fn();
    render(<RangeSlider {...defaultProps} onChange={onChange} />);
    const startInput = screen.getByLabelText(/start/i);
    fireEvent.change(startInput, { target: { value: '20' } });
    expect(onChange).toHaveBeenCalledWith(20, 80);
  });

  it('prevents start from crossing end', () => {
    const onChange = vi.fn();
    render(<RangeSlider {...defaultProps} onChange={onChange} />);
    const startInput = screen.getByLabelText(/start/i);
    fireEvent.change(startInput, { target: { value: '85' } });
    expect(onChange).toHaveBeenCalledWith(79.5, 80);
  });

  it('has aria-valuenow attributes', () => {
    render(<RangeSlider {...defaultProps} />);
    const startInput = screen.getByLabelText(/start/i);
    expect(startInput.getAttribute('aria-valuenow')).toBe('10');
  });
});
