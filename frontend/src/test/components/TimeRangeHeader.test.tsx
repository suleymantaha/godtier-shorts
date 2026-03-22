import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { TimeRangeHeader } from '../../components/TimeRangeHeader';

describe('TimeRangeHeader', () => {
  it('shows total duration in seconds and minutes', () => {
    render(<TimeRangeHeader endTime={150} startTime={30} title="Kesim Araligi" />);

    expect(screen.getByText(/30\.0s - 150\.0s/i)).toBeInTheDocument();
    expect(screen.getByText(/\[Total: 120\.0s \| 2\.0 min\]/i)).toBeInTheDocument();
  });

  it('renders extra labels for page-specific metadata', () => {
    render(<TimeRangeHeader endTime={70} extraLabel="[8 segment]" startTime={10} title="Duzenlenecek aralik" />);

    expect(screen.getByText(/\[8 segment\]/i)).toBeInTheDocument();
  });
});
