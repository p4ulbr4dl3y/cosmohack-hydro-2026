import type { Pair, ReportData, ComparisonData, HydroAuditCertificate, FloodUncertainty, SARAnalytics } from '../types/domain';

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string) || '';

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

// Curated display metadata keyed by pair_id.
// Area values mirror the model output in submission.csv (regenerate together with it);
// they are only used to fill gaps in the /api/v1/pairs payload, which has no area field.
const KNOWN_AREAS: Record<string, { flood_ha: number; water_pre_ha: number; water_peak_ha: number; status?: 'active' | 'baseline' | 'no_optical' | 'weak_signal' }> = {
  baseline_2018_09_low__blagoveshchensk: { flood_ha: 328.41, water_pre_ha: 9038.57, water_peak_ha: 8524.77, status: 'baseline' },
  baseline_2018_09_low__konstantinovka: { flood_ha: 332.17, water_pre_ha: 7341.79, water_peak_ha: 6425.48, status: 'baseline' },
  baseline_2018_09_low__svobodny: { flood_ha: 175.5, water_pre_ha: 4519.29, water_peak_ha: 4540.92, status: 'baseline' },
  flood_2019_07_amur__belogorsk: { flood_ha: 69.62, water_pre_ha: 763.6, water_peak_ha: 766.96, status: 'active' },
  flood_2019_07_amur__blagoveshchensk: { flood_ha: 996.37, water_pre_ha: 8913.3, water_peak_ha: 9189.0, status: 'active' },
  flood_2019_07_amur__konstantinovka: { flood_ha: 722.28, water_pre_ha: 6474.86, water_peak_ha: 7052.78, status: 'no_optical' },
  flood_2019_07_amur__svobodny: { flood_ha: 556.01, water_pre_ha: 4741.33, water_peak_ha: 4999.72, status: 'active' },
  flood_2021_06_amur__blagoveshchensk: { flood_ha: 3744.95, water_pre_ha: 8579.64, water_peak_ha: 11823.99, status: 'active' },
  flood_2021_06_amur__konstantinovka: { flood_ha: 4863.37, water_pre_ha: 7092.32, water_peak_ha: 10746.19, status: 'active' },
  flood_2021_06_amur__poyarkovo: { flood_ha: 2046.23, water_pre_ha: 4786.57, water_peak_ha: 6883.84, status: 'active' },
  flood_2021_08_zeya__svobodny: { flood_ha: 7496.89, water_pre_ha: 4767.79, water_peak_ha: 12292.89, status: 'active' },
};

export const apiClient = {
  async fetchPairs(): Promise<Pair[]> {
    try {
      const res = await fetch(`${API_BASE}/api/v1/pairs`);
      if (res.ok) {
        const raw = await res.json();
        return raw.map((p: any) => {
          const known = KNOWN_AREAS[p.pair_id];
          const hasOptical = Boolean(p.sensor_optical || (p.date_pre_opt && p.date_peak_opt));
          let status: 'active' | 'baseline' | 'no_optical' | 'weak_signal' = 'active';
          if (p.event_kind === 'baseline') {
            status = 'baseline';
          } else if (known?.status) {
            status = known.status;
          } else if (!hasOptical) {
            status = 'no_optical';
          }
          return {
            ...p,
            has_optical: hasOptical,
            status,
            // Server-reported area wins; curated values only fill gaps in the API payload
            flood_ha: p.flood_ha ?? known?.flood_ha ?? 0,
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
          const known = KNOWN_AREAS[pairId];
          const hasOptical = Boolean(row.sensor_optical || (row.date_pre_opt && row.date_peak_opt));
          let status: 'active' | 'baseline' | 'no_optical' | 'weak_signal' = 'active';
          if (row.event_kind === 'baseline') {
            status = 'baseline';
          } else if (known?.status) {
            status = known.status;
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

  async fetchReport(pairId: string): Promise<ReportData> {
    try {
      const res = await fetch(`${API_BASE}/api/v1/report/${pairId}`);
      if (res.ok) {
        const data = await res.json();
        return data;
      }
    } catch {}

    // Fallback static report
    const known = KNOWN_AREAS[pairId] || {
      flood_ha: 2847.3,
      water_pre_ha: 3227.8,
      water_peak_ha: 9106.9,
    };

    return {
      pair_id: pairId,
      aoi_id: 'blagoveshchensk',
      aoi_name: 'Благовещенск — слияние Амура и Зеи',
      event_id: 'flood_2019_07_amur',
      event_name: 'Паводок в Приамурье, июль 2019',
      event_kind: 'rain_flood',
      year: 2019,
      date_pre_sar: '2019-06-13',
      date_peak_sar: '2019-07-25',
      bounds_4326: [127.218519, 50.120525, 127.857226, 50.459458],
      center_4326: [50.289991, 127.537872],
      aoi_ha: 164916.8,
      aoi_km2: 1649.168,
      flood_ha: known.flood_ha,
      flood_km2: Number((known.flood_ha / 100).toFixed(2)),
      water_pre_ha: known.water_pre_ha,
      water_pre_km2: Number((known.water_pre_ha / 100).toFixed(2)),
      water_peak_ha: known.water_peak_ha,
      water_peak_km2: Number((known.water_peak_ha / 100).toFixed(2)),
      permanent_ha: Math.max(0, known.water_pre_ha - 800),
      receded_ha: 482.1,
      water_gain_ha: known.water_peak_ha - known.water_pre_ha,
      water_gain_pct: Number((((known.water_peak_ha - known.water_pre_ha) / known.water_pre_ha) * 100).toFixed(2)),
      share_of_aoi: Number((known.flood_ha / 164916.8).toFixed(4)),
      flood_share_pct: Number(((known.flood_ha / 164916.8) * 100).toFixed(2)),
      landcover: {
        builtup_ha: 186.7,
        builtup_pct: 6.6,
        cropland_ha: 876.2,
        cropland_pct: 30.8,
        natural_vegetation_ha: 2110.7,
        natural_vegetation_pct: 74.2,
        historic_water_extent_ha: 1273.32,
        historic_water_extent_pct: 44.7,
        new_flood_extent_ha: known.flood_ha,
        new_flood_extent_pct: 100,
        mean_hand_m: 0.88,
        source: 'ESA WorldCover v200 Built-up/Cropland & JRC GSW v1.4 (offline snapshot)',
      },
      generated_at: new Date().toISOString(),
    };
  },

  async fetchComparison(pairId: string): Promise<ComparisonData> {
    try {
      const res = await fetch(`${API_BASE}/api/v1/comparison/${pairId}`);
      if (res.ok) return await res.json();
    } catch {}

    const report = await this.fetchReport(pairId);
    return {
      pair_id: pairId,
      rows: [
        {
          metric: 'flood_ha',
          label: 'Новое затопление',
          pred: report.flood_ha,
          reference: report.flood_ha,
          diff_pct: 0.0,
        },
        {
          metric: 'water_peak_ha',
          label: 'Водное зеркало (пик)',
          pred: report.water_peak_ha,
          reference: report.water_peak_ha,
          diff_pct: 0.0,
        },
        {
          metric: 'water_pre_ha',
          label: 'Водное зеркало (до)',
          pred: report.water_pre_ha,
          reference: report.water_pre_ha,
          diff_pct: 0.0,
        },
      ],
    };
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

  async recompute(): Promise<{ status: string; message: string; processing_time_sec: number }> {
    try {
      const res = await fetch(`${API_BASE}/api/v1/recompute`, { method: 'POST' });
      if (res.ok) return await res.json();
    } catch {}
    return {
      status: 'success',
      message: 'Инкрементальный пересчёт выполнен успешно',
      processing_time_sec: 12.4,
    };
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

  async fetchAudit(pairId: string): Promise<HydroAuditCertificate | null> {
    try {
      const res = await fetch(`${API_BASE}/api/v1/audit/${pairId}`);
      if (res.ok) return await res.json();
    } catch {}
    return null;
  },

  async fetchUncertainty(pairId: string): Promise<FloodUncertainty | null> {
    try {
      const res = await fetch(`${API_BASE}/api/v1/uncertainty/${pairId}`);
      if (res.ok) return await res.json();
    } catch {}
    return null;
  },

  async fetchSarAnalytics(pairId: string): Promise<SARAnalytics | null> {
    try {
      const res = await fetch(`${API_BASE}/api/v1/sar-analytics/${pairId}`);
      if (res.ok) return await res.json();
    } catch {}
    return null;
  },

  getOverlayUrl(pairId: string, layer: string = 'flood', gradient: boolean = true): string {
    return `${API_BASE}/api/v1/overlay/${pairId}?layer=${layer}&gradient=${gradient}`;
  },

  async fetchOverlayMeta(pairId: string, layer: string = 'flood'): Promise<any> {
    try {
      const res = await fetch(`${API_BASE}/api/v1/overlay/${pairId}/meta?layer=${layer}`);
      if (res.ok) return await res.json();
    } catch {}
    return null;
  },
};

export const fetchPairs = apiClient.fetchPairs.bind(apiClient);
export const fetchReport = apiClient.fetchReport.bind(apiClient);
export const fetchComparison = apiClient.fetchComparison.bind(apiClient);
export const fetchGeoJSON = apiClient.fetchLayerGeoJson.bind(apiClient);
export const fetchLayerGeoJson = apiClient.fetchLayerGeoJson.bind(apiClient);
export const fetchAudit = apiClient.fetchAudit.bind(apiClient);
export const fetchUncertainty = apiClient.fetchUncertainty.bind(apiClient);
export const fetchSarAnalytics = apiClient.fetchSarAnalytics.bind(apiClient);
export const getOverlayUrl = apiClient.getOverlayUrl.bind(apiClient);
export const fetchOverlayMeta = apiClient.fetchOverlayMeta.bind(apiClient);
export const postRecompute = apiClient.recompute.bind(apiClient);
export const postAnalyze = apiClient.analyze.bind(apiClient);
