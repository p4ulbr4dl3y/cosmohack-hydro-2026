// @vitest-environment jsdom
import { describe, it, expect } from 'vitest';
import React from 'react';
import { render, screen } from '@testing-library/react';
import { HydrographChart } from '../components/analytics/HydrographChart';

// Recharts needs a ResizeObserver in jsdom
global.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
} as any;

describe('HydrographChart component', () => {
  it('plots the real SAR water extents passed in as props', () => {
    const { container } = render(
      <HydrographChart
        datePre="2019-06-13"
        datePeak="2019-07-25"
        waterPreHa={8913.3}
        waterPeakHa={9189}
      />
    );

    // Real delta in days between the SAR scenes, not a hardcoded label
    expect(screen.getByText('SAR: 42 суток')).toBeDefined();
    expect(screen.getByText('водное зеркало, га')).toBeDefined();
    expect(container.querySelector('.recharts-responsive-container')).not.toBeNull();
  });

  it('renders an explicit empty state when extents are missing', () => {
    render(<HydrographChart datePre="2019-06-13" datePeak="2019-07-25" />);

    expect(screen.getByText('Недостаточно данных для построения гидрографа')).toBeDefined();
  });

  it('never fabricates the S1↔S2 offset label', () => {
    render(
      <HydrographChart
        datePre="2019-06-13"
        datePeak="2019-07-25"
        waterPreHa={8913.3}
        waterPeakHa={9189}
      />
    );

    expect(screen.queryByText(/Δt S1↔S2/)).toBeNull();
  });
});