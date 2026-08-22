import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { Paywall } from '../../components/paywall/Paywall';

describe('Paywall', () => {
  it('uses the real candidate count and keeps expensive production features locked', () => {
    render(<Paywall candidateCount={2} />);

    expect(screen.getByText('2 güçlü Short bulundu')).toBeInTheDocument();
    expect(screen.getByText('1080p export')).toBeInTheDocument();
    expect(screen.getAllByText('Smart tracking')).toHaveLength(2);
    expect(screen.getByText('Batch render')).toBeInTheDocument();
    expect(screen.getByText('Download')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Üretim seçeneklerini aç' })).toHaveAttribute('href', '/?tab=billing');
  });
});
