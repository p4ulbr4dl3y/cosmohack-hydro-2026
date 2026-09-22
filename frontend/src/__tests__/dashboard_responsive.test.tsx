// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from 'vitest';
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { Dashboard } from '../pages/Dashboard';

// Мок ResizeObserver для Recharts в jsdom
global.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
} as any;

// Мок MapContainer, чтобы избежать требований Leaflet к canvas в модульном тесте
vi.mock('../components/map/MapContainer', () => ({
  MapContainer: () => <div data-testid="mock-map">Map Container</div>,
}));

// Мок API-клиента
vi.mock('../api/client', () => ({
  apiClient: {
    fetchPairs: vi.fn().mockResolvedValue([
      {
        pair_id: 'flood_2019_07_amur__blagoveshchensk',
        aoi_name: 'Благовещенск',
        event_id: 'flood_2019_07_amur',
        event_kind: 'rain_flood',
        date_pre_sar: '2019-06-13',
        date_peak_sar: '2019-07-25',
        flood_ha: 2847.3,
        water_peak_ha: 9106.9,
        water_pre_ha: 6259.6,
      },
      {
        pair_id: 'flood_2019_07_amur__belogorsk',
        aoi_name: 'Белогорск',
        event_id: 'flood_2019_07_amur',
        event_kind: 'rain_flood',
        date_pre_sar: '2019-06-13',
        date_peak_sar: '2019-07-25',
        flood_ha: 315.4,
        water_peak_ha: 928.0,
        water_pre_ha: 673.7,
      },
    ]),
    fetchReport: vi.fn().mockResolvedValue({
      pair_id: 'flood_2019_07_amur__blagoveshchensk',
      event_id: 'flood_2019_07_amur',
      event_name: 'Паводок в Приамурье, июль 2019',
      aoi_name: 'Благовещенск',
      flood_ha: 2847.3,
      flood_km2: 28.473,
      water_peak_ha: 9106.9,
      water_peak_km2: 91.069,
      water_pre_ha: 6259.6,
      water_pre_km2: 62.596,
      share_of_aoi: 0.0173,
      date_pre_sar: '2019-06-13',
      date_peak_sar: '2019-07-25',
    }),
    recompute: vi.fn().mockResolvedValue({ status: 'success' }),
    fetchAudit: vi.fn().mockResolvedValue(null),
    fetchUncertainty: vi.fn().mockResolvedValue(null),
    fetchSarAnalytics: vi.fn().mockResolvedValue(null),
    fetchOfficialMetrics: vi.fn().mockResolvedValue(null),
    validateSubmission: vi.fn().mockResolvedValue(null),
    fetchCarbonImpact: vi.fn().mockResolvedValue(null),
    getOverlayUrl: vi.fn().mockReturnValue(''),
    fetchOverlayMeta: vi.fn().mockResolvedValue(null),
  },
}));

describe('Dashboard responsive tabs and layout', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders Dashboard layout with Topbar, Map, and status bar', async () => {
    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    );

    expect(screen.getByTestId('mock-map')).toBeDefined();
    expect(screen.getByText(/HydroWatch/)).toBeDefined();
    expect(screen.getByText(/API: online/)).toBeDefined();
  });

  it('provides mobile bottom navigation with Map, Pairs, and Analytics tabs', async () => {
    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    );

    const bottomNav = screen.getByRole('navigation');
    expect(bottomNav).toBeDefined();

    const mapTabBtn = screen.getAllByRole('button', { name: /^Карта$/i })[0];
    const pairsTabBtn = screen.getAllByRole('button', { name: /Наблюдения/i })[0];
    const analyticsTabBtn = screen.getAllByRole('button', { name: /Аналитика/i })[0];

    expect(mapTabBtn).toBeDefined();
    expect(pairsTabBtn).toBeDefined();
    expect(analyticsTabBtn).toBeDefined();
  });

  it('switches to pairs tab on mobile navigation click and back to map on return button', async () => {
    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    );

    const pairsTabBtn = screen.getAllByRole('button', { name: /Наблюдения/i })[0];
    fireEvent.click(pairsTabBtn);

    // На мобильном должна отображаться кнопка возврата к карте
    const backBtn = screen.getByRole('button', { name: /К карте/i });
    expect(backBtn).toBeDefined();

    fireEvent.click(backBtn);
    expect(screen.getByTestId('mock-map')).toBeDefined();
  });

  it('switches to analytics tab on mobile navigation click', async () => {
    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    );

    const analyticsTabBtn = screen.getAllByRole('button', { name: /Аналитика/i })[0];
    fireEvent.click(analyticsTabBtn);

    expect(screen.getByText('Аналитическая панель')).toBeDefined();
    expect(screen.getByText('Скачать отчёт (PDF)')).toBeDefined();
  });
});
