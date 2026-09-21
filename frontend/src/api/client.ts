import type { Pair, ReportData, ComparisonData } from '../types/domain';

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string) || '';

export interface RecomputeResult {
  status: string;
  message?: string;
  processing_time_sec?: number;
  memory_peak_gb?: number;
  timestamp_utc?: string;
  pairs?: string[];
}

function parseCsvLine(line: string): string[] {
  const result: string[] = [];
  let cur = '';
  let inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const c = line[i];
    if (c === '"') {
      if (inQuotes && line[i + 1] === '"') {
        cur += '"';
        i++;
      } else {
        inQuotes = !inQuotes;
      }
    } else if (c === ',' && !inQuotes) {
      result.push(cur.trim());
      cur = '';
    } else {
      cur += c;
    }
  }
  result.push(cur.trim());
  return result;
}

// Curated display status per pair_id, used only for sidebar categorisation.
// Measurement values are deliberately NOT stored here: the API is the single
// source of truth for areas, and a local number would be a fabricated figure.
const KNOWN_AREAS: Record<string, 'active' | 'baseline' | 'no_optical' | 'weak_signal'> = {
  baseline_2018_09_low__blagoveshchensk: 'baseline',
  baseline_2018_09_low__konstantinovka: 'baseline',
  baseline_2018_09_low__svobodny: 'baseline',
  flood_2019_07_amur__belogorsk: 'active',
  flood_2019_07_amur__blagoveshchensk: 'active',
  flood_2019_07_amur__konstantinovka: 'no_optical',
  flood_2019_07_amur__svobodny: 'active',
  flood_2021_06_amur__blagoveshchensk: 'active',
  flood_2021_06_amur__konstantinovka: 'active',
  flood_2021_06_amur__poyarkovo: 'active',
  flood_2021_08_zeya__svobodny: 'active',
};

export const apiClient = {
  async fetchPairs(): Promise<Pair[]> {
    try {
      const res = await fetch(`${API_BASE}/api/v1/pairs`);
      if (res.ok) {
        const raw = await res.json();
        return raw.map((p: any) => {
          const knownStatus = KNOWN_AREAS[p.pair_id];
          const hasOptical = Boolean(p.sensor_optical || (p.date_pre_opt && p.date_peak_opt));
          let status: 'active' | 'baseline' | 'no_optical' | 'weak_signal' = 'active';
          if (p.event_kind === 'baseline') {
            status = 'baseline';
          } else if (knownStatus) {
            status = knownStatus;
          } else if (!hasOptical) {
            status = 'no_optical';
          }
          return {
            ...p,
            has_optical: hasOptical,
            status,
            // Areas are omitted when the API does not report them; never invented locally.
            flood_ha: p.flood_ha ?? undefined,
          };
        });
      }
    } catch {
      // Fallback to static csv
    }

    // Static fallback: read /data/pairs.csv
    try {
      const csvRes = await fetch('/data/pairs.csv');
      if (csvRes.ok) {
        const text = await csvRes.text();
        const lines = text.trim().split('\n');
        const header = parseCsvLine(lines[0]);
        const pairs: Pair[] = [];

        for (let i = 1; i < lines.length; i++) {
          if (!lines[i].trim()) continue;
          const cols = parseCsvLine(lines[i]);
          const row: Record<string, string> = {};
          header.forEach((h, idx) => {
            row[h] = cols[idx] || '';
          });

          const pairId = row.pair_id;
          const knownStatus = KNOWN_AREAS[pairId];
          const hasOptical = Boolean(row.sensor_optical || (row.date_pre_opt && row.date_peak_opt));
          let status: 'active' | 'baseline' | 'no_optical' | 'weak_signal' = 'active';
          if (row.event_kind === 'baseline') {
            status = 'baseline';
          } else if (knownStatus) {
            status = knownStatus;
          } else if (!hasOptical) {
            status = 'no_optical';
          }

          pairs.push({
            pair_id: pairId,
            aoi_id: row.aoi_id,
            aoi_name: row.aoi_name,
            event_id: row.event_id,
            event_name: row.event_name,
            event_kind: row.event_kind,
            year: Number(row.year) || 2019,
            sensor_sar: row.sensor_sar,
            sensor_optical: row.sensor_optical,
            date_pre_sar: row.date_pre_sar,
            date_peak_sar: row.date_peak_sar,
            date_pre_opt: row.date_pre_opt,
            date_peak_opt: row.date_peak_opt,
            aoi_km2: Number(row.aoi_km2) || 1250,
            aoi_ha: Math.round((Number(row.aoi_km2) || 1250) * 100),
            center_4326: [50.2796, 127.5405],
            bounds_4326: [127.1, 50.1, 128.0, 50.5],
            has_optical: hasOptical,
            status,
          });
        }
        return pairs;
      }
    } catch (e) {
      console.error('Failed to load static pairs.csv', e);
    }

    return [];
  },

  async fetchAoi(): Promise<any> {
    try {
      const res = await fetch(`${API_BASE}/api/v1/aoi`);
      if (res.ok) return await res.json();
    } catch {}
    const fallback = await fetch('/data/aoi.geojson');
    return await fallback.json();
  },

  async fetchVectorLayer(name: string): Promise<any> {
    try {
      const res = await fetch(`${API_BASE}/api/v1/vectors/${name}`);
      if (res.ok) return await res.json();
    } catch {}
    const fallback = await fetch(`/data/${name}.geojson`);
    return await fallback.json();
  },

  async fetchReport(pairId: string): Promise<ReportData | null> {
    try {
      const res = await fetch(`${API_BASE}/api/v1/report/${pairId}`);
      if (res.ok) {
        return await res.json();
      }
      console.error(`fetchReport(${pairId}) failed with status ${res.status}`);
    } catch (e) {
      console.error(`fetchReport(${pairId}) failed`, e);
    }
    // No data means no report: substituting invented numbers would fabricate measurements.
    return null;
  },

  async fetchComparison(pairId: string): Promise<ComparisonData | null> {
    try {
      const res = await fetch(`${API_BASE}/api/v1/comparison/${pairId}`);
      if (res.ok) return await res.json();
      console.error(`fetchComparison(${pairId}) failed with status ${res.status}`);
    } catch (e) {
      console.error(`fetchComparison(${pairId}) failed`, e);
    }
    // Reference rows must come from the server; synthesising them from the
    // prediction would always report a fake "0.0% deviation".
    return null;
  },

  async fetchLayerGeoJson(pairId: string, layer: string): Promise<any> {
    try {
      const res = await fetch(`${API_BASE}/api/v1/layers/${pairId}/${layer}`);
      if (res.ok) return await res.json();
    } catch {}
    try {
      const res = await fetch(`${API_BASE}/api/v1/geojson/${pairId}?layer=${layer}`);
      if (res.ok) return await res.json();
    } catch {}
    if (layer === 'water_pre' || layer === 'water_peak') {
      try {
        const hydro = await this.fetchVectorLayer('hydrography_osm');
        if (hydro) return hydro;
      } catch {}
    }
    return null;
  },

  async fetchGeoJSON(pairId: string, layer: string): Promise<any> {
    return this.fetchLayerGeoJson(pairId, layer);
  },

  async recompute(): Promise<RecomputeResult> {
    try {
      const res = await fetch(`${API_BASE}/api/v1/recompute`, { method: 'POST' });
      if (res.ok) return await res.json();
      console.error(`recompute failed with status ${res.status}`);
      return { status: 'error', message: `Пересчёт не выполнен (HTTP ${res.status})` };
    } catch (e) {
      console.error('recompute failed', e);
      // Never report a fabricated success or timing when the request did not happen.
      return { status: 'error', message: 'Пересчёт не выполнен: сервис недоступен' };
    }
  },

  async analyze(pairId: string): Promise<any> {
    try {
      const res = await fetch(`${API_BASE}/api/v1/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pair_id: pairId }),
      });
      if (res.ok) return await res.json();
    } catch {}
    return await this.fetchReport(pairId);
  },
};

export const fetchPairs = apiClient.fetchPairs.bind(apiClient);
export const fetchReport = apiClient.fetchReport.bind(apiClient);
export const fetchComparison = apiClient.fetchComparison.bind(apiClient);
export const fetchGeoJSON = apiClient.fetchLayerGeoJson.bind(apiClient);
export const fetchLayerGeoJson = apiClient.fetchLayerGeoJson.bind(apiClient);
export const postRecompute = apiClient.recompute.bind(apiClient);
export const postAnalyze = apiClient.analyze.bind(apiClient);
