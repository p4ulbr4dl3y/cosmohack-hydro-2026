// @vitest-environment jsdom
import { describe, it, expect } from 'vitest';
import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ApiDocs, ENDPOINTS } from '../pages/ApiDocs';

describe('ApiDocs ENDPOINTS catalog verification', () => {
  it('registers the full API catalog including undocumented-before endpoints', () => {
    // Каталог покрывает все публичные маршруты сервиса, включая ранее не
    // документированные (сцены, оверлеи, аудит, неопределённость, метео, EDA).
    expect(ENDPOINTS.length).toBe(34);
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

  it('ensures API endpoints begin with /api/v1 while system pages stay at the root', () => {
    ENDPOINTS.forEach((ep) => {
      // /health и /eda живут вне префикса /api/v1 по устройству сервиса.
      const isSystemPage = ep.id === 'root_health' || ep.id === 'eda';
      expect(ep.path.startsWith(isSystemPage ? '/' : '/api/v1')).toBe(true);
    });
  });

  it('generates valid URLs via buildUrl without crashing', () => {
    const dummyParams = {
      pair_id: 'flood_2019_07_amur__blagoveshchensk',
      layer: 'flood',
      layer_name: 'hydrography_osm',
      format: 'geojson',
      mode: 'sar_vv',
      window: 'peak',
      task_id: 'task-demo-0001',
      confidence_level: '0.95',
    };

    ENDPOINTS.forEach((ep) => {
      const url = ep.buildUrl(dummyParams);
      expect(url).toBeDefined();
      const isSystemPage = ep.id === 'root_health' || ep.id === 'eda';
      expect(url.startsWith(isSystemPage ? '/' : '/api/v1')).toBe(true);
    });
  });

  it('generates executable cURL commands', () => {
    const dummyParams = {
      pair_id: 'flood_2019_07_amur__blagoveshchensk',
      layer: 'flood',
      layer_name: 'hydrography_osm',
      format: 'geojson',
      mode: 'sar_vv',
      window: 'peak',
      task_id: 'task-demo-0001',
      confidence_level: '0.95',
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

  it('documents the endpoints the map, report and dashboard actually call', () => {
    const ids = ENDPOINTS.map((e) => e.id);
    // Без этих маршрутов подложка карты, отчёт и индикатор состояния опираются
    // на недокументированный контракт.
    ['scene', 'scene_meta', 'geojson', 'shapefile', 'geotiff', 'overlay', 'overlay_meta',
     'report_csv', 'report_mchs', 'audit', 'uncertainty', 'sar_analytics', 'predict_status',
     'meteo', 'root_health'].forEach((id) => {
      expect(ids).toContain(id);
    });
  });

  it('renders cURL example section in light theme mode', () => {
    const { container } = render(
      React.createElement(MemoryRouter, null, React.createElement(ApiDocs, null))
    );
    expect(screen.getByText('cURL-пример')).toBeDefined();
    const curlPre = container.querySelector('pre.text-slate-800');
    expect(curlPre).toBeDefined();
    // Подтверждает отсутствие класса тёмного фона у контейнера cURL
    expect(container.querySelector('.bg-\\[\\#0F172A\\]')).toBeNull();
  });
});
