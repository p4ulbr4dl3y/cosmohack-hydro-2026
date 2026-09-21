import { describe, it, expect } from 'vitest';
import * as fs from 'node:fs';
import * as path from 'node:path';

function parseCsv(content: string): Array<Record<string, string>> {
  const lines = content.trim().split(/\r?\n/).filter((l) => l.trim().length > 0);
  if (lines.length < 2) return [];

  function parseLine(line: string): string[] {
    const fields: string[] = [];
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
        fields.push(cur.trim());
        cur = '';
      } else {
        cur += c;
      }
    }
    fields.push(cur.trim());
    return fields;
  }

  const header = parseLine(lines[0]);
  return lines.slice(1).map((line) => {
    const values = parseLine(line);
    const row: Record<string, string> = {};
    header.forEach((col, idx) => {
      row[col] = values[idx] || '';
    });
    return row;
  });
}

describe('Data Integrity & pairs.csv Validation', () => {
  const rootCsvPath = path.resolve(__dirname, '../../../hydrowatch_amur/pairs.csv');
  const publicCsvPath = path.resolve(__dirname, '../../public/data/pairs.csv');
  const aoiGeoJsonPath = path.resolve(__dirname, '../../public/data/aoi.geojson');

  const EXPECTED_PAIR_IDS = [
    'baseline_2018_09_low__blagoveshchensk',
    'baseline_2018_09_low__konstantinovka',
    'baseline_2018_09_low__svobodny',
    'flood_2019_07_amur__belogorsk',
    'flood_2019_07_amur__blagoveshchensk',
    'flood_2019_07_amur__konstantinovka',
    'flood_2019_07_amur__svobodny',
    'flood_2021_06_amur__blagoveshchensk',
    'flood_2021_06_amur__konstantinovka',
    'flood_2021_06_amur__poyarkovo',
    'flood_2021_08_zeya__svobodny',
  ];

  it('data/pairs.csv exists and is readable', () => {
    expect(fs.existsSync(rootCsvPath), `File not found: ${rootCsvPath}`).toBe(true);
    const content = fs.readFileSync(rootCsvPath, 'utf-8');
    expect(content.length).toBeGreaterThan(0);
  });

  it('contains exactly 11 distinct pairs matching expected pair_ids', () => {
    const content = fs.readFileSync(rootCsvPath, 'utf-8');
    const rows = parseCsv(content);

    expect(rows.length).toBe(11);
    const pairIds = rows.map((r) => r.pair_id);
    expect(new Set(pairIds).size).toBe(11);

    EXPECTED_PAIR_IDS.forEach((id) => {
      expect(pairIds).toContain(id);
    });
  });

  it('synchronizes data/pairs.csv and frontend/public/data/pairs.csv', () => {
    if (fs.existsSync(publicCsvPath)) {
      const rootRows = parseCsv(fs.readFileSync(rootCsvPath, 'utf-8'));
      const publicRows = parseCsv(fs.readFileSync(publicCsvPath, 'utf-8'));
      expect(publicRows.length).toBe(rootRows.length);
      const rootIds = rootRows.map((r) => r.pair_id).sort();
      const publicIds = publicRows.map((r) => r.pair_id).sort();
      expect(publicIds).toEqual(rootIds);
    }
  });

  it('validates each pair has valid metadata, aoi_id, and dates', () => {
    const rows = parseCsv(fs.readFileSync(rootCsvPath, 'utf-8'));
    const isoDatePattern = /^\d{4}-\d{2}-\d{2}$/;

    rows.forEach((row) => {
      expect(row.pair_id).toBeTruthy();
      expect(row.aoi_id).toBeTruthy();
      expect(row.aoi_name).toBeTruthy();
      expect(row.event_id).toBeTruthy();
      expect(row.event_name).toBeTruthy();

      // Validate SAR dates
      expect(row.date_pre_sar).toMatch(isoDatePattern);
      expect(row.date_peak_sar).toMatch(isoDatePattern);
      expect(new Date(row.date_pre_sar).getTime()).toBeLessThanOrEqual(
        new Date(row.date_peak_sar).getTime()
      );

      // Optical dates (if optical sensor present)
      if (row.sensor_optical) {
        expect(row.date_pre_opt).toMatch(isoDatePattern);
        expect(row.date_peak_opt).toMatch(isoDatePattern);
        expect(new Date(row.date_pre_opt).getTime()).toBeLessThanOrEqual(
          new Date(row.date_peak_opt).getTime()
        );
      }

      // aoi_km2 must be positive number
      const km2 = parseFloat(row.aoi_km2);
      expect(isNaN(km2)).toBe(false);
      expect(km2).toBeGreaterThan(0);
    });
  });

  it('validates AOI coordinates and geographic bounds in Amur region', () => {
    expect(fs.existsSync(aoiGeoJsonPath), `AOI geojson missing at: ${aoiGeoJsonPath}`).toBe(true);
    const aoiData = JSON.parse(fs.readFileSync(aoiGeoJsonPath, 'utf-8'));
    expect(aoiData.type).toBe('FeatureCollection');
    expect(Array.isArray(aoiData.features)).toBe(true);

    const rows = parseCsv(fs.readFileSync(rootCsvPath, 'utf-8'));
    const aoiFeaturesById = new Map<string, any>();
    aoiData.features.forEach((f: any) => {
      if (f.properties?.aoi_id) {
        aoiFeaturesById.set(f.properties.aoi_id, f);
      }
    });

    // Each pair's aoi_id must exist in aoi.geojson with valid polygon coordinates in Amur basin
    rows.forEach((row) => {
      const feature = aoiFeaturesById.get(row.aoi_id);
      expect(feature, `AOI feature for ${row.aoi_id} not found in aoi.geojson`).toBeDefined();

      const geom = feature.geometry;
      expect(geom.type).toBe('Polygon');
      expect(Array.isArray(geom.coordinates)).toBe(true);
      expect(geom.coordinates.length).toBeGreaterThan(0);

      // Check coordinates lie within Amur oblast bounding region (~48..55°N, 125..135°E)
      geom.coordinates[0].forEach(([lon, lat]: [number, number]) => {
        expect(typeof lon).toBe('number');
        expect(typeof lat).toBe('number');
        expect(lon).toBeGreaterThanOrEqual(125.0);
        expect(lon).toBeLessThanOrEqual(135.0);
        expect(lat).toBeGreaterThanOrEqual(48.0);
        expect(lat).toBeLessThanOrEqual(55.0);
      });

      if (feature.properties.lat && feature.properties.lon) {
        expect(feature.properties.lat).toBeGreaterThanOrEqual(48.0);
        expect(feature.properties.lat).toBeLessThanOrEqual(55.0);
        expect(feature.properties.lon).toBeGreaterThanOrEqual(125.0);
        expect(feature.properties.lon).toBeLessThanOrEqual(135.0);
      }
    });
  });
});
