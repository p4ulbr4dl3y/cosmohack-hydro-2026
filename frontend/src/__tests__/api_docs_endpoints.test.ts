// @vitest-environment jsdom
import { describe, it, expect } from 'vitest';
import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ApiDocs, ENDPOINTS } from '../pages/ApiDocs';

describe('ApiDocs ENDPOINTS catalog verification', () => {
  it('registers all 15 required API endpoints', () => {
    expect(ENDPOINTS.length).toBe(15);
  });

  it('guarantees unique endpoint IDs', () => {
    const ids = ENDPOINTS.map((e) => e.id);
    const uniqueIds = new Set(ids);
    expect(uniqueIds.size).toBe(ids.length);
  });

  it('has valid HTTP methods (GET or POST)', () => {
    ENDPOINTS.forEach((ep) => {
      expect(['GET', 'POST']).toContain(ep.method);
    });
  });

  it('ensures all paths begin with /api/v1', () => {
    ENDPOINTS.forEach((ep) => {
      expect(ep.path.startsWith('/api/v1')).toBe(true);
    });
  });

  it('generates valid URLs via buildUrl without crashing', () => {
    const dummyParams = {
      pair_id: 'flood_2019_07_amur__blagoveshchensk',
      layer: 'flood',
      layer_name: 'hydrography_osm',
      format: 'geojson',
    };

    ENDPOINTS.forEach((ep) => {
      const url = ep.buildUrl(dummyParams);
      expect(url).toBeDefined();
      expect(url.startsWith('/api/v1')).toBe(true);
    });
  });

  it('generates executable cURL commands', () => {
    const dummyParams = {
      pair_id: 'flood_2019_07_amur__blagoveshchensk',
      layer: 'flood',
      layer_name: 'hydrography_osm',
      format: 'geojson',
    };

    ENDPOINTS.forEach((ep) => {
      const curl = ep.curlTemplate(dummyParams, '{"test": 1}');
      expect(curl).toBeDefined();
      expect(curl.startsWith('curl ')).toBe(true);
      expect(curl).toContain(ep.method);
    });
  });

  it('provides valid non-empty response examples', () => {
    ENDPOINTS.forEach((ep) => {
      expect(ep.responseExample).toBeDefined();
      expect(ep.responseExample.length).toBeGreaterThan(0);
    });
  });

  it('has valid HTTP error codes >= 400', () => {
    ENDPOINTS.forEach((ep) => {
      ep.errorCodes.forEach((err) => {
        expect(err.code).toBeGreaterThanOrEqual(400);
        expect(err.description).toBeTruthy();
      });
    });
  });

  it('contains critical hydrological core endpoints', () => {
    const ids = ENDPOINTS.map((e) => e.id);
    expect(ids).toContain('events');
    expect(ids).toContain('pairs');
    expect(ids).toContain('aoi');
    expect(ids).toContain('predict');
    expect(ids).toContain('report');
    expect(ids).toContain('comparison');
    expect(ids).toContain('ablation');
    expect(ids).toContain('layers_geojson');
    expect(ids).toContain('layers_by_name');
    expect(ids).toContain('vectors');
    expect(ids).toContain('export_vectors');
    expect(ids).toContain('export_report');
    expect(ids).toContain('recompute');
    expect(ids).toContain('health');
  });

  it('renders cURL example section in light theme mode', () => {
    const { container } = render(
      React.createElement(MemoryRouter, null, React.createElement(ApiDocs, null))
    );
    expect(screen.getByText('cURL-пример')).toBeDefined();
    const curlPre = container.querySelector('pre.text-slate-800');
    expect(curlPre).toBeDefined();
    // Confirms no dark background class on cURL container
    expect(container.querySelector('.bg-\\[\\#0F172A\\]')).toBeNull();
  });
});
