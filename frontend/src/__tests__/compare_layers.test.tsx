// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from 'vitest';
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { Compare } from '../pages/Compare';
import { apiClient } from '../api/client';

// Mock Leaflet
vi.mock('leaflet', () => {
  const mapMock = {
    on: vi.fn(),
    setView: vi.fn(),
    fitBounds: vi.fn(),
    remove: vi.fn(),
    addLayer: vi.fn(),
    removeLayer: vi.fn(),
    hasLayer: vi.fn().mockReturnValue(true),
    getCenter: vi.fn().mockReturnValue({ lat: 50.28, lng: 127.53 }),
    getZoom: vi.fn().mockReturnValue(11),
  };

  return {
    default: {
      map: vi.fn().mockReturnValue(mapMock),
      tileLayer: vi.fn().mockReturnValue({ addTo: vi.fn().mockReturnThis() }),
      geoJSON: vi.fn().mockReturnValue({
        addTo: vi.fn().mockReturnThis(),
        getBounds: vi.fn().mockReturnValue({
          isValid: vi.fn().mockReturnValue(true),
        }),
      }),
    },
  };
});

describe('Compare page and layer visualization', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders Compare container, watermark badges, and return button', async () => {
    render(
      <MemoryRouter initialEntries={['/compare/flood_2019_07_amur__blagoveshchensk']}>
        <Routes>
          <Route path="/compare/:pairId" element={<Compare />} />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText('Назад к дашборду')).toBeDefined();
    expect(screen.getByText(/Сравнение до \/ пик/)).toBeDefined();
    expect(screen.getAllByText(/ДО ·/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/ПИК ·/).length).toBeGreaterThan(0);
    expect(screen.getByText('новое затопление')).toBeDefined();
  });

  it('provides layer visibility toggles for flood, peak, pre-water, and hydrography', async () => {
    render(
      <MemoryRouter initialEntries={['/compare/flood_2019_07_amur__blagoveshchensk']}>
        <Routes>
          <Route path="/compare/:pairId" element={<Compare />} />
        </Routes>
      </MemoryRouter>
    );

    const floodToggle = screen.getByText('Затопление');
    const peakToggle = screen.getByText('Зеркало (пик)');
    const preToggle = screen.getByText('Вода до');
    const hydroToggle = screen.getByText('Реки (OSM)');

    expect(floodToggle).toBeDefined();
    expect(peakToggle).toBeDefined();
    expect(preToggle).toBeDefined();
    expect(hydroToggle).toBeDefined();

    // Toggle a layer off and verify click doesn't error
    fireEvent.click(floodToggle);
    fireEvent.click(preToggle);
    fireEvent.click(hydroToggle);
  });

  it('provides basemap mode switches (SAR, MSI, Маски)', async () => {
    render(
      <MemoryRouter initialEntries={['/compare/flood_2019_07_amur__blagoveshchensk']}>
        <Routes>
          <Route path="/compare/:pairId" element={<Compare />} />
        </Routes>
      </MemoryRouter>
    );

    const sarBtn = screen.getByText('SAR');
    const msiBtn = screen.getByText('MSI');
    const masksBtn = screen.getByText(/маски/i);

    expect(sarBtn).toBeDefined();
    expect(msiBtn).toBeDefined();
    expect(masksBtn).toBeDefined();

    fireEvent.click(sarBtn);
    fireEvent.click(msiBtn);
    fireEvent.click(masksBtn);
  });

  it('resets slider position when clicking reset button', async () => {
    render(
      <MemoryRouter initialEntries={['/compare/flood_2019_07_amur__blagoveshchensk']}>
        <Routes>
          <Route path="/compare/:pairId" element={<Compare />} />
        </Routes>
      </MemoryRouter>
    );

    const resetBtn = screen.getByText('Сбросить');
    expect(resetBtn).toBeDefined();
    fireEvent.click(resetBtn);
  });

  it('falls back to hydrography_osm when water_pre/water_peak are requested offline', async () => {
    const mockHydro = {
      type: 'FeatureCollection',
      features: [{ type: 'Feature', properties: { name: 'Amur River' } }],
    };

    vi.spyOn(global, 'fetch').mockImplementation((url: any) => {
      if (String(url).includes('hydrography_osm')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockHydro),
        } as any);
      }
      return Promise.reject(new Error('Network offline'));
    });

    const preResult = await apiClient.fetchLayerGeoJson('test_pair', 'water_pre');
    expect(preResult).toBeDefined();
    expect(preResult.features[0].properties.name).toBe('Amur River');

    const peakResult = await apiClient.fetchLayerGeoJson('test_pair', 'water_peak');
    expect(peakResult).toBeDefined();
    expect(peakResult.features[0].properties.name).toBe('Amur River');
  });
});
