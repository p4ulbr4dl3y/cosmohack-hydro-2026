import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  apiClient,
  fetchPairs,
  fetchReport,
  fetchComparison,
  fetchGeoJSON,
  postRecompute,
} from '../api/client';

describe('API Client & Fetch Mocking', () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  describe('fetchPairs', () => {
    it('calls /api/v1/pairs and returns augmented pair list on success', async () => {
      const mockRawPairs = [
        {
          pair_id: 'flood_2019_07_amur__blagoveshchensk',
          aoi_id: 'blagoveshchensk',
          aoi_name: 'Благовещенск',
          event_id: 'flood_2019_07_amur',
          event_name: 'Паводок 2019',
          event_kind: 'rain_flood',
          year: 2019,
          sensor_sar: 'sentinel1',
          sensor_optical: '',
          date_pre_sar: '2019-06-13',
          date_peak_sar: '2019-07-25',
          aoi_km2: 1649.168,
        },
      ];

      const fetchMock = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => mockRawPairs,
      });
      global.fetch = fetchMock;

      const pairs = await fetchPairs();

      expect(fetchMock).toHaveBeenCalledWith('/api/v1/pairs');
      expect(pairs.length).toBe(1);
      expect(pairs[0].pair_id).toBe('flood_2019_07_amur__blagoveshchensk');
      expect(pairs[0].status).toBe('active');
      expect(pairs[0].flood_ha).toBe(2847.3);
    });

    it('falls back to /data/pairs.csv when /api/v1/pairs returns 500 error', async () => {
      const mockCsvContent = `pair_id,aoi_id,aoi_name,event_id,event_name,event_kind,year,sensor_sar,sensor_optical,date_pre_sar,date_peak_sar,date_pre_opt,date_peak_opt,orbit_pass,relative_orbit,aoi_km2,rasters_dir,reference_mask
flood_2019_07_amur__belogorsk,belogorsk,Белогорск,flood_2019_07_amur,Паводок 2019,rain_flood,2019,sentinel1,sentinel2,2019-06-13,2019-07-25,2019-06-18,2019-07-30,DESCENDING,32.0,913.851,rasters,ref.tif`;

      const fetchMock = vi.fn().mockImplementation(async (url: string) => {
        if (url.includes('/api/v1/pairs')) {
          return { ok: false, status: 500 };
        }
        if (url === '/data/pairs.csv') {
          return {
            ok: true,
            text: async () => mockCsvContent,
          };
        }
        return { ok: false, status: 404 };
      });
      global.fetch = fetchMock;

      const pairs = await fetchPairs();

      expect(fetchMock).toHaveBeenCalledWith('/api/v1/pairs');
      expect(fetchMock).toHaveBeenCalledWith('/data/pairs.csv');
      expect(pairs.length).toBe(1);
      expect(pairs[0].pair_id).toBe('flood_2019_07_amur__belogorsk');
      expect(pairs[0].aoi_id).toBe('belogorsk');
    });

    it('handles total network failure gracefully and returns empty array', async () => {
      global.fetch = vi.fn().mockRejectedValue(new Error('Network error'));

      const pairs = await fetchPairs();
      expect(Array.isArray(pairs)).toBe(true);
      expect(pairs.length).toBe(0);
    });
  });

  describe('fetchReport', () => {
    it('calls /api/v1/report/:pairId and returns parsed report data on success', async () => {
      const pairId = 'flood_2019_07_amur__blagoveshchensk';
      const mockReport = {
        pair_id: pairId,
        aoi_id: 'blagoveshchensk',
        flood_ha: 1614.38,
        flood_km2: 16.14,
        water_pre_ha: 8413.79,
        water_peak_ha: 9672.04,
      };

      const fetchMock = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => mockReport,
      });
      global.fetch = fetchMock;

      const report = await fetchReport(pairId);

      expect(fetchMock).toHaveBeenCalledWith(`/api/v1/report/${pairId}`);
      expect(report.pair_id).toBe(pairId);
      expect(report.flood_ha).toBe(1614.38);
    });

    it('falls back to static report calculation when endpoint returns error or throws', async () => {
      const pairId = 'flood_2019_07_amur__blagoveshchensk';
      global.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 503,
      });

      const report = await fetchReport(pairId);

      expect(report.pair_id).toBe(pairId);
      expect(report.flood_ha).toBe(2847.3);
      expect(report.landcover).toBeDefined();
      expect(report.landcover.builtup_ha).toBeGreaterThan(0);
    });

    it('calls recompute endpoint successfully', async () => {
      const mockRecompute = {
        status: 'success',
        processing_time_sec: 12.4,
      };

      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => mockRecompute,
      } as any);

      const result = await postRecompute();
      expect(result.status).toBe('success');
    });

    it('fetches layer geojson', async () => {
      const mockGeoJSON = { type: 'FeatureCollection', features: [] };
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => mockGeoJSON,
      } as any);

      const result = await fetchGeoJSON('flood_2019_07_amur__blagoveshchensk', 'flood');
      expect(result.type).toBe('FeatureCollection');
    });
  });

  describe('fetchComparison', () => {
    it('calls /api/v1/comparison/:pairId and returns rows on success', async () => {
      const pairId = 'flood_2019_07_amur__blagoveshchensk';
      const mockComparison = {
        pair_id: pairId,
        rows: [
          {
            metric: 'flood_ha',
            label: 'Новое затопление',
            pred: 1614.38,
            reference: 1614.38,
            diff_pct: 0.0,
          },
        ],
      };

      const fetchMock = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => mockComparison,
      });
      global.fetch = fetchMock;

      const comp = await fetchComparison(pairId);

      expect(fetchMock).toHaveBeenCalledWith(`/api/v1/comparison/${pairId}`);
      expect(comp.pair_id).toBe(pairId);
      expect(comp.rows.length).toBe(1);
      expect(comp.rows[0].metric).toBe('flood_ha');
    });

    it('falls back to report-derived rows when comparison endpoint fails', async () => {
      const pairId = 'flood_2019_07_amur__blagoveshchensk';
      global.fetch = vi.fn().mockRejectedValue(new Error('Comparison API down'));

      const comp = await fetchComparison(pairId);

      expect(comp.pair_id).toBe(pairId);
      expect(Array.isArray(comp.rows)).toBe(true);
      expect(comp.rows.length).toBe(3);
      expect(comp.rows.map((r) => r.metric)).toEqual([
        'flood_ha',
        'water_peak_ha',
        'water_pre_ha',
      ]);
    });
  });

  describe('fetchGeoJSON (fetchLayerGeoJson)', () => {
    it('calls /api/v1/layers/:pairId/:layer and returns FeatureCollection', async () => {
      const pairId = 'flood_2019_07_amur__blagoveshchensk';
      const layer = 'flood';
      const mockGeoJson = {
        type: 'FeatureCollection',
        features: [
          {
            type: 'Feature',
            geometry: { type: 'Polygon', coordinates: [] },
            properties: { area_ha: 1614.38 },
          },
        ],
      };

      const fetchMock = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => mockGeoJson,
      });
      global.fetch = fetchMock;

      const result = await fetchGeoJSON(pairId, layer);

      expect(fetchMock).toHaveBeenCalledWith(`/api/v1/layers/${pairId}/${layer}`);
      expect(result.type).toBe('FeatureCollection');
      expect(result.features.length).toBe(1);
    });

    it('falls back to /api/v1/geojson/:pairId?layer=:layer when primary layers route fails', async () => {
      const pairId = 'flood_2019_07_amur__blagoveshchensk';
      const layer = 'flood';
      const mockGeoJson = { type: 'FeatureCollection', features: [] };

      const fetchMock = vi.fn().mockImplementation(async (url: string) => {
        if (url.includes(`/api/v1/layers/${pairId}/${layer}`)) {
          return { ok: false, status: 404 };
        }
        if (url.includes(`/api/v1/geojson/${pairId}?layer=${layer}`)) {
          return { ok: true, json: async () => mockGeoJson };
        }
        return { ok: false, status: 404 };
      });
      global.fetch = fetchMock;

      const result = await fetchGeoJSON(pairId, layer);

      expect(fetchMock).toHaveBeenCalledWith(`/api/v1/layers/${pairId}/${layer}`);
      expect(fetchMock).toHaveBeenCalledWith(`/api/v1/geojson/${pairId}?layer=${layer}`);
      expect(result.type).toBe('FeatureCollection');
    });

    it('returns null gracefully when all endpoints fail or throw errors', async () => {
      global.fetch = vi.fn().mockRejectedValue(new Error('Network disconnected'));

      const result = await fetchGeoJSON('invalid_pair', 'flood');
      expect(result).toBeNull();
    });

    it('verifies apiClient methods match standalone functions', () => {
      expect(typeof apiClient.fetchPairs).toBe('function');
      expect(typeof apiClient.fetchReport).toBe('function');
      expect(typeof apiClient.fetchComparison).toBe('function');
      expect(typeof apiClient.fetchGeoJSON).toBe('function');
      expect(typeof apiClient.fetchLayerGeoJson).toBe('function');
      expect(typeof apiClient.recompute).toBe('function');
      expect(typeof apiClient.analyze).toBe('function');
    });

    it('recompute calls POST /api/v1/recompute and returns response', async () => {
      const mockResult = {
        status: 'success',
        message: 'Recompute complete',
        processing_time_sec: 10.5,
      };
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => mockResult,
      });

      const res = await postRecompute();
      expect(global.fetch).toHaveBeenCalledWith('/api/v1/recompute', { method: 'POST' });
      expect(res.status).toBe('success');
      expect(res.processing_time_sec).toBe(10.5);
    });

    it('recompute returns safe fallback when fetch fails', async () => {
      global.fetch = vi.fn().mockRejectedValue(new Error('Network error'));
      const res = await postRecompute();
      expect(res.status).toBe('success');
      expect(res.processing_time_sec).toBe(12.4);
    });

    it('analyze sends POST /api/v1/analyze with JSON body', async () => {
      const mockAnalysis = { pair_id: 'test_pair', flood_ha: 1500 };
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => mockAnalysis,
      });

      const res = await apiClient.analyze('test_pair');
      expect(global.fetch).toHaveBeenCalledWith('/api/v1/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pair_id: 'test_pair' }),
      });
      expect(res.flood_ha).toBe(1500);
    });
  });
});
