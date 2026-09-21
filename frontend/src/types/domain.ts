export interface Pair {
  pair_id: string;
  aoi_id: string;
  aoi_name: string;
  event_id: string;
  event_name: string;
  event_kind: 'flood' | 'baseline' | string;
  year: number;
  sensor_sar: string;
  sensor_optical: string;
  date_pre_sar: string;
  date_peak_sar: string;
  date_pre_opt?: string;
  date_peak_opt?: string;
  aoi_km2: number;
  aoi_ha: number;
  bounds_4326?: [number, number, number, number];
  center_4326?: [number, number];
  status?: 'active' | 'baseline' | 'no_optical' | 'weak_signal';
  has_optical?: boolean;
  flood_ha?: number;
}

export interface LandcoverItem {
  class_id?: number;
  class_name: string;
  name?: string;
  area_ha: number;
  percentage: number;
}

export interface LandcoverBreakdown {
  builtup_ha: number;
  builtup_pct: number;
  cropland_ha?: number;
  cropland_pct?: number;
  natural_vegetation_ha: number;
  natural_vegetation_pct: number;
  historic_water_extent_ha: number;
  historic_water_extent_pct: number;
  new_flood_extent_ha: number;
  new_flood_extent_pct: number;
  mean_hand_m: number;
  source: string;
  items?: LandcoverItem[];
}

export interface ReportData {
  pair_id: string;
  aoi_id: string;
  aoi_name: string;
  event_id: string;
  event_name: string;
  event_kind: string;
  year: number;
  date_pre_sar: string;
  date_peak_sar: string;
  date_pre_opt?: string;
  date_peak_opt?: string;
  sensor_sar?: string;
  sensor_optical?: string;
  bounds_4326: [number, number, number, number];
  center_4326: [number, number];
  aoi_ha: number;
  aoi_km2: number;
  flood_ha: number;
  flood_km2: number;
  water_pre_ha: number;
  water_pre_km2: number;
  water_peak_ha: number;
  water_peak_km2: number;
  permanent_ha: number;
  receded_ha: number;
  water_gain_ha: number;
  water_gain_pct: number;
  share_of_aoi: number;
  flood_share_pct: number;
  landcover: LandcoverBreakdown;
  generated_at?: string;
}

export interface ComparisonRow {
  metric: string;
  label: string;
  pred: number;
  reference: number;
  diff_pct: number;
}

export interface ComparisonData {
  pair_id: string;
  rows: ComparisonRow[];
}

export interface LayerState {
  flood: boolean;
  water_peak: boolean;
  water_pre: boolean;
  permanent: boolean;
  receded: boolean;
  osm_hydro: boolean;
  hydrosheds: boolean;
  aoi_boundary: boolean;
  opacity: number;
}

export type BasemapType = 'sar_vv' | 'sar_vh' | 'msi_true' | 'msi_false' | 'carto_light';
export type ViewMode = 'map' | 'report' | 'compare';
