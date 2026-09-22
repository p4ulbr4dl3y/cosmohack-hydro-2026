// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from 'vitest';
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { renderHook } from '@testing-library/react';
import { LayerControl } from '../components/map/LayerControl';
import { Legend } from '../components/map/Legend';
import { useUiStore } from '../store/uiStore';

// Leaflet в jsdom не имеет canvas-контекста: модуль подложек сцены мокается целиком,
// а проверяется только контракт вызовов (какая сцена и какое окно запрошены).
vi.mock('leaflet', () => ({
  default: {
    map: vi.fn(),
    tileLayer: vi.fn().mockReturnValue({ addTo: vi.fn().mockReturnThis() }),
    geoJSON: vi.fn(),
    imageOverlay: vi.fn().mockReturnValue({ addTo: vi.fn().mockReturnThis(), remove: vi.fn() }),
    canvas: vi.fn().mockReturnValue({}),
    control: { zoom: vi.fn().mockReturnValue({ addTo: vi.fn() }) },
  },
}));

const fetchSceneMeta = vi.fn();
vi.mock('../api/client', () => ({
  apiClient: {
    fetchSceneMeta: (...args: unknown[]) => fetchSceneMeta(...args),
    getSceneUrl: (pairId: string, mode: string, window: string) =>
      `/api/v1/scene/${pairId}/${mode}?window=${window}`,
  },
}));

import { loadSceneOverlay } from '../lib/sceneOverlay';
import { isSceneBasemap, SCENE_BASEMAPS } from '../types/domain';

const fakeMap = {
  getPane: vi.fn().mockReturnValue(null),
  createPane: vi.fn().mockReturnValue({ style: {} }),
  removeLayer: vi.fn(),
} as any;

describe('Derived water layers (permanent, receded)', () => {
  beforeEach(() => {
    useUiStore.setState({
      layers: {
        flood: true,
        water_peak: true,
        water_pre: true,
        permanent: true,
        receded: false,
        osm_hydro: true,
        hydrosheds: false,
        aoi_boundary: true,
        opacity: 0.6,
      },
    });
  });

  it('offers a checkbox for permanent water and receded water', () => {
    render(<LayerControl />);

    expect(screen.getByText('Постоянная вода')).toBeDefined();
    expect(screen.getByText('Убыль воды')).toBeDefined();
  });

  it('toggles the receded layer through the store', () => {
    render(<LayerControl />);

    // Раньше «Убыль воды» рисовалась только в легенде и включить её было нечем.
    const label = screen.getByText('Убыль воды');
    const checkbox = label.closest('label')!.querySelector('input') as HTMLInputElement;
    expect(checkbox.checked).toBe(false);

    fireEvent.click(checkbox);
    expect(useUiStore.getState().layers.receded).toBe(true);
  });

  it('toggles the permanent layer through the store', () => {
    render(<LayerControl />);

    const label = screen.getByText('Постоянная вода');
    const checkbox = label.closest('label')!.querySelector('input') as HTMLInputElement;
    expect(checkbox.checked).toBe(true);

    fireEvent.click(checkbox);
    expect(useUiStore.getState().layers.permanent).toBe(false);
  });

  it('keeps legend entries and layer checkboxes in sync', () => {
    const { unmount } = render(<Legend aoiKm2={1500} />);
    const legendLabels = ['Новое затопление (flood)', 'Вода на пик', 'Вода на до', 'Постоянная вода', 'Убыль воды'];
    legendLabels.forEach((label) => expect(screen.getByText(label)).toBeDefined());
    unmount();

    render(<LayerControl />);
    ['Новое затопление', 'Вода на пик', 'Вода на до', 'Постоянная вода', 'Убыль воды'].forEach(
      (label) => expect(screen.getByText(label)).toBeDefined()
    );
  });
});

describe('Scene basemap wiring', () => {
  beforeEach(() => {
    fetchSceneMeta.mockReset();
  });

  it('treats only Sentinel scene modes as image overlays', () => {
    SCENE_BASEMAPS.forEach((mode) => expect(isSceneBasemap(mode)).toBe(true));
    // Значение по умолчанию стора обязано быть сценой, а не нейтральной подложкой.
    expect(isSceneBasemap(useUiStore.getState().basemap)).toBe(true);
  });

  it('requests the peak window by default and the pre window when asked', async () => {
    fetchSceneMeta.mockResolvedValue({
      bounds: [
        [50.1, 127.2],
        [50.4, 127.8],
      ],
      label: 'Sentinel-1 SAR VV (пик)',
      source: 'S1_peak_2019-07-25.tif',
    });

    await loadSceneOverlay(fakeMap, 'flood_2019_07_amur__blagoveshchensk', 'sar_vv');
    expect(fetchSceneMeta).toHaveBeenCalledWith(
      'flood_2019_07_amur__blagoveshchensk',
      'sar_vv',
      'peak'
    );

    await loadSceneOverlay(fakeMap, 'flood_2019_07_amur__blagoveshchensk', 'sar_vv', 'pre');
    expect(fetchSceneMeta).toHaveBeenLastCalledWith(
      'flood_2019_07_amur__blagoveshchensk',
      'sar_vv',
      'pre'
    );
  });

  it('returns null instead of a placeholder tile when the scene is unavailable', async () => {
    fetchSceneMeta.mockResolvedValue(null);

    // Оптические пары без данных не должны подменяться чужой картинкой.
    const overlay = await loadSceneOverlay(fakeMap, 'flood_2019_07_amur__blagoveshchensk', 'msi_true');
    expect(overlay).toBeNull();
  });

  it('stops using unrelated carto/arcgis tiles for SAR and MSI labels', async () => {
    const fs = await import('node:fs');
    const path = await import('node:path');
    const containerSrc = fs.readFileSync(
      path.resolve(__dirname, '../components/map/MapContainer.tsx'),
      'utf-8'
    );

    expect(containerSrc).not.toContain('rastertiles/voyager');
    expect(containerSrc).not.toContain('World_Imagery');
    expect(containerSrc).toContain('loadSceneOverlay');
  });
});

describe('Hydrograph tick formatting', () => {
  it('keeps tick labels distinguishable when the span is under 1000 ha', async () => {
    const { formatWaterTick } = await import('../components/analytics/HydrographChart');

    // Разброс 87 га при значениях около 9 000 га раньше схлопывался в «9k | 9k | 9k».
    const labels = [9027.18, 9070, 9114.37].map((v) => formatWaterTick(v, 87.19));
    expect(new Set(labels).size).toBe(3);
    expect(labels).not.toContain('9k');
  });

  it('switches to kilounits only for genuinely large spans', async () => {
    const { formatWaterTick } = await import('../components/analytics/HydrographChart');

    expect(formatWaterTick(9000, 5000)).toBe('9k');
    expect(formatWaterTick(12500, 5000)).toBe('13k');
    expect(formatWaterTick(0, 5000)).toBe('0');
  });
});