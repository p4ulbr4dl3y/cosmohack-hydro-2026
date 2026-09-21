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
export type GradientOverlayMode = 'none' | 'flood' | 'water_peak' | 'water_pre';

export interface MerkleLeafItem {
  index?: number;
  key?: string;
  name?: string;
  hash: string;
  description?: string;
}

export interface HydroAuditCertificate {
  certificate_id: string;
  pair_id: string;
  aoi_id: string;
  issued_at?: string;
  timestamp?: string;
  merkle_root?: string;
  merkle_root_sha256?: string;
  leaf_count?: number;
  status?: string;
  verified?: boolean;
  algorithm?: string;
  signature_hash?: string;
  summary?: Record<string, any>;
  leaves?: MerkleLeafItem[];
  inputs_hash_sha256?: string;
  parameters_hash_sha256?: string;
  results_hash_sha256?: string;
}

export interface FloodUncertainty {
  pair_id: string;
  area_ha: number;
  confidence_level: number;
  lower_bound_ha: number;
  upper_bound_ha: number;
  margin_ha: number;
  relative_uncertainty_pct: number;
  sigma_effective_ha: number;
  effective_n_pixels: number;
  spatial_correlation: number;
}

export interface SARAnalytics {
  pair_id: string;
  water_fraction: number;
  water_area_ha: number;
  mean_vv_db: number;
  mean_vh_db: number;
  mean_vh_vv_ratio: number;
  radar_contrast_db: number;
  cloud_penetration_verified: boolean;
  double_bounce_fraction: number;
}

export interface PairScoreDetail {
  pair_id: string;
  event_kind: string;
  aoi_ha: number;
  flood_sub_ha: number;
  flood_ref_ha: number;
  water_peak_sub_ha: number;
  water_peak_ref_ha: number;
  water_pre_sub_ha: number;
  water_pre_ref_ha: number;
  q_flood: number;
  q_water_peak: number;
  q_water_pre: number;
  spec_score?: number | null;
  flood_abs_diff_ha: number;
  flood_rel_diff_pct: number;
  raster_ha?: number | null;
  raster_csv_discrepancy_pct?: number | null;
}

export interface OfficialMetrics {
  score: number;
  q_flood: number;
  q_water_peak: number;
  q_water_pre: number;
  spec_base: number;
  num_events: number;
  num_baselines: number;
  technical_points: number;
  details: PairScoreDetail[];
}

export interface SubmissionDiscrepancy {
  pair_id: string;
  csv_flood_ha: number;
  raster_flood_ha: number;
  discrepancy_pct: number;
  is_within_2_percent: boolean;
}

export interface SubmissionValidation {
  is_valid: boolean;
  num_pairs: number;
  passed_checks: string[];
  errors: string[];
  warnings: string[];
  discrepancies: SubmissionDiscrepancy[];
}

export interface CarbonCreditPotential {
  is_available: boolean;
  status: string;
  E_proj_tCO2e: number;
  E_base_tCO2e: number;
  LK_tCO2e: number;
  R_tCO2e: number;
  H_tCO2e: number;
  H_over_R?: number | null;
  UNC_deduction_rate: number;
  R_adj_tCO2e: number;
  buffer_reserve_B_tCO2e: number;
  Q_credits: number;
  fractional_remainder: number;
  valuations_rub: Record<string | number, number>;
  area_ha: number;
  delta_t_years: number;
}

export interface FloodCarbonImpact {
  pair_id: string;
  flood_ha: number;
  biomass_loss_dry_matter_t: number;
  carbon_loss_tC: number;
  emissions_equivalent_tCO2e: number;
  cropland_loss_tC: number;
  forest_loss_tC: number;
  credit_potential: CarbonCreditPotential;
  notes: string;
}

