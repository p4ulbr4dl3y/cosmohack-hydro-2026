// @vitest-environment jsdom
import { describe, it, expect } from 'vitest';
import React from 'react';
import { render, screen } from '@testing-library/react';
import { KpiCards } from '../components/analytics/KpiCards';
import { LandcoverChart } from '../components/analytics/LandcoverChart';
import type { ReportData, LandcoverBreakdown } from '../types/domain';

const mockReport: ReportData = {
  pair_id: 'flood_2019_07_amur__blagoveshchensk',
  event_id: 'flood_2019_07_amur',
  event_name: 'Паводок в Приамурье, июль 2019',
  aoi_id: 'blagoveshchensk',
  aoi_name: 'Благовещенск',
  year: 2019,
  date_pre_sar: '2019-06-13',
  date_peak_sar: '2019-07-25',
  aoi_km2: 1649.17,
  aoi_ha: 164917,
  flood_ha: 2847.3,
  flood_km2: 28.473,
  water_peak_ha: 9106.9,
  water_peak_km2: 91.069,
  water_pre_ha: 6259.6,
  water_pre_km2: 62.596,
  receded_ha: 120.4,
  receded_km2: 1.204,
  share_of_aoi: 0.0173,
  flood_share_pct: 1.73,
  water_peak_share_pct: 5.52,
  water_pre_share_pct: 3.8,
  metrics_source: 'consensus',
  bounds_4326: [127.2, 50.1, 127.8, 50.5],
  center_4326: [50.3, 127.5],
};

const mockLandcover: LandcoverBreakdown = {
  total_ha: 2847.3,
  items: [
    { class_id: 10, class_name: 'Лес', area_ha: 1200, percentage: 42.1 },
    { class_id: 40, class_name: 'Сельхоз', area_ha: 800, percentage: 28.1 },
    { class_id: 80, class_name: 'Вода', area_ha: 200, percentage: 7.0 },
  ],
};

describe('KpiCards component', () => {
  it('renders loading skeleton when isLoading is true or report is null', () => {
    const { container } = render(<KpiCards report={null} isLoading={true} />);
    expect(container.querySelectorAll('.animate-pulse').length).toBe(4);
  });

  it('renders all 4 cards: flood, water peak, water pre, and receded', () => {
    render(<KpiCards report={mockReport} isLoading={false} />);

    expect(screen.getByText('НОВОЕ ЗАТОПЛЕНИЕ')).toBeDefined();
    expect(screen.getByText(/Водное зеркало \(пик\)/)).toBeDefined();
    expect(screen.getByText(/Водное зеркало \(до\)/)).toBeDefined();
    expect(screen.getByText('Убыль воды')).toBeDefined();
  });

  it('displays computed share of AOI percent', () => {
    render(<KpiCards report={mockReport} isLoading={false} />);
    expect(screen.getByText(/1\.73% от AOI/)).toBeDefined();
  });
});

describe('LandcoverChart component', () => {
  it('renders custom landcover breakdown items when provided', () => {
    render(<LandcoverChart landcover={mockLandcover} />);

    expect(screen.getByText('Лес')).toBeDefined();
    expect(screen.getByText('Сельхоз')).toBeDefined();
    expect(screen.getByText('Вода')).toBeDefined();
  });

  it('falls back to default ESA classes when landcover is undefined', () => {
    render(<LandcoverChart landcover={undefined} />);

    expect(screen.getByText('Forest')).toBeDefined();
    expect(screen.getByText('Cropland')).toBeDefined();
    expect(screen.getByText('Grassland')).toBeDefined();
  });
});
