// @vitest-environment jsdom
import { describe, it, expect } from 'vitest';
import React from 'react';
import { render, screen } from '@testing-library/react';
import { ReportDocument } from '../components/report/ReportDocument';
import type { ReportData, ComparisonData } from '../types/domain';

const mockReport: ReportData = {
  pair_id: 'flood_2019_07_amur__blagoveshchensk',
  event_id: 'flood_2019_07_amur',
  event_name: 'Паводок в Приамурье, июль 2019',
  aoi_id: 'blagoveshchensk',
  aoi_name: 'Благовещенск — слияние Амура и Зеи',
  year: 2019,
  date_pre_sar: '2019-06-13',
  date_peak_sar: '2019-07-25',
  date_pre_opt: '2019-06-18',
  date_peak_opt: '2019-07-30',
  aoi_km2: 1649.17,
  aoi_ha: 164917,
  flood_ha: 2847.3,
  flood_km2: 28.473,
  water_peak_ha: 9106.9,
  water_peak_km2: 91.069,
  water_pre_ha: 6259.6,
  water_pre_km2: 62.596,
  receded_ha: 0,
  receded_km2: 0,
  share_of_aoi: 0.0173,
  flood_share_pct: 1.73,
  water_peak_share_pct: 5.52,
  water_pre_share_pct: 3.8,
  metrics_source: 'consensus',
  bounds_4326: [127.2, 50.1, 127.8, 50.5],
  center_4326: [50.3, 127.5],
  landcover: {
    builtup_ha: 186.7,
    builtup_pct: 6.6,
    cropland_ha: 876.2,
    cropland_pct: 30.8,
    natural_vegetation_ha: 1234.5,
    natural_vegetation_pct: 43.4,
    historic_water_extent_ha: 1273.32,
    historic_water_extent_pct: 44.7,
    new_flood_extent_ha: 2847.3,
    new_flood_extent_pct: 100,
    mean_hand_m: 0.88,
    source: 'ESA WorldCover v200 Built-up/Cropland & JRC GSW v1.4',
  },
};

const mockComparison: ComparisonData = {
  pair_id: 'flood_2019_07_amur__blagoveshchensk',
  aoi_id: 'blagoveshchensk',
  rows: [
    {
      metric: 'flood_ha',
      pred: 2847.3,
      reference: 2847.3,
      diff_ha: 0,
      diff_pct: 0,
      description: 'Новое затопление',
    },
    {
      metric: 'water_peak_ha',
      pred: 9106.9,
      reference: 9106.9,
      diff_ha: 0,
      diff_pct: 0,
      description: 'Водное зеркало на пик',
    },
    {
      metric: 'water_pre_ha',
      pred: 6259.6,
      reference: 6259.6,
      diff_ha: 0,
      diff_pct: 0,
      description: 'Водное зеркало до события',
    },
  ],
};

describe('ReportDocument component', () => {
  it('renders report header with brand and title', () => {
    render(<ReportDocument report={mockReport} comparison={mockComparison} forPdf={true} />);

    expect(screen.getAllByText('HydroWatch').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Паводок в Приамурье, июль 2019').length).toBeGreaterThan(0);
    expect(screen.getAllByText(/КосмоХакатон 2026/).length).toBeGreaterThan(0);
  });

  it('renders AOI centre as lat/lon (lat first) without a hardcoded placeholder', () => {
    render(<ReportDocument report={mockReport} comparison={mockComparison} forPdf={true} />);

    expect(screen.getByText('50.3000° N, 127.5000° E')).toBeDefined();
  });

  it('formats generated_at as a UTC timestamp and falls back to a dash', () => {
    const { unmount } = render(
      <ReportDocument
        report={{ ...mockReport, generated_at: '2026-09-21T20:21:00+00:00' }}
        comparison={mockComparison}
        forPdf={true}
      />
    );
    expect(screen.getByText('Сгенерировано: 2026-09-21 20:21 UTC')).toBeDefined();
    unmount();

    render(<ReportDocument report={mockReport} comparison={mockComparison} forPdf={true} />);
    expect(screen.getByText('Сгенерировано: —')).toBeDefined();
  });

  it('reports NO optical coverage when dates are absent but marks it available otherwise', () => {
    const { unmount } = render(
      <ReportDocument report={mockReport} comparison={mockComparison} forPdf={true} />
    );
    expect(screen.getByText('ПРИГОДНА')).toBeDefined();
    expect(screen.getByText('2019-06-18 → 2019-07-30')).toBeDefined();
    unmount();

    render(
      <ReportDocument
        report={{ ...mockReport, date_pre_opt: '', date_peak_opt: '' }}
        comparison={mockComparison}
        forPdf={true}
      />
    );
    expect(screen.getByText('НЕТ ОПТИКИ')).toBeDefined();
    expect(screen.getByText('нет перекрывающей сцены')).toBeDefined();
  });

  it('renders input data section with Sentinel-1 and Sentinel-2 details', () => {
    render(<ReportDocument report={mockReport} comparison={mockComparison} forPdf={true} />);

    expect(screen.getByText('Sentinel-1 (SAR)')).toBeDefined();
    expect(screen.getByText('Sentinel-2 (MSI)')).toBeDefined();
    expect(screen.getByText('ПРИГОДНА')).toBeDefined();
  });

  it('renders the raw sensor code as a readable SAR sensor name', () => {
    render(
      <ReportDocument
        report={{ ...mockReport, sensor_sar: 'sentinel1' }}
        comparison={mockComparison}
        forPdf={true}
      />
    );

    expect(screen.getByText('Sentinel-1')).toBeDefined();
  });

  it('displays correct KPI titles and sections', () => {
    render(<ReportDocument report={mockReport} comparison={mockComparison} forPdf={true} />);

    expect(screen.getByText(/НОВОЕ ЗАТОПЛЕНИЕ/)).toBeDefined();
    expect(screen.getByText(/ВОДНОЕ ЗЕРКАЛО \(ПИК\)/)).toBeDefined();
    expect(screen.getByText(/ВОДНОЕ ЗЕРКАЛО \(ДО\)/)).toBeDefined();

    // Check that numeric text nodes are rendered
    expect(screen.getAllByText(/2[\s\u00A0\u202F]847/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/9[\s\u00A0\u202F]106/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/6[\s\u00A0\u202F]259/i).length).toBeGreaterThan(0);
  });

  it('renders reference comparison table rows', () => {
    render(<ReportDocument report={mockReport} comparison={mockComparison} forPdf={true} />);

    expect(screen.getByText('СРАВНЕНИЕ С ЭТАЛОНОМ')).toBeDefined();
    expect(screen.getAllByText('flood_ha').length).toBeGreaterThan(0);
    expect(screen.getAllByText('water_peak_ha').length).toBeGreaterThan(0);
  });

  it('renders landcover classes table from ESA WorldCover', () => {
    render(<ReportDocument report={mockReport} comparison={mockComparison} forPdf={true} />);

    expect(screen.getAllByText('Лес / растительность').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Сельхозугодья / Пашни').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Застройка / Населенные пункты').length).toBeGreaterThan(0);
  });

  it('renders methodology and copyright footer', () => {
    render(<ReportDocument report={mockReport} comparison={mockComparison} forPdf={true} />);

    expect(screen.getByText(/5\. МЕТОДИКА И АЛГОРИТМЫ ВЫЧИСЛЕНИЯ/)).toBeDefined();
    expect(screen.getAllByText(/Данные Copernicus © ESA/).length).toBeGreaterThan(0);
  });

  it('contains discrete pages (data-pdf-page) with clean section separation to prevent map splitting', () => {
    const { container } = render(
      <ReportDocument report={mockReport} comparison={mockComparison} forPdf={true} />
    );

    const pages = container.querySelectorAll('[data-pdf-page]');
    expect(pages.length).toBe(2);

    const page1 = container.querySelector('[data-pdf-page="1"]');
    const page2 = container.querySelector('[data-pdf-page="2"]');

    expect(page1).toBeDefined();
    expect(page2).toBeDefined();

    // Section 1 and 2 in Page 1
    expect(page1?.textContent).toContain('1. ИСХОДНЫЕ ДАННЫЕ');
    expect(page1?.textContent).toContain('2. РЕЗУЛЬТАТЫ ГИДРОЛОГИЧЕСКОГО АНАЛИЗА');

    // Section 3 (Map) and Section 4 in Page 2
    expect(page2?.textContent).toContain('3. КАРТА ЗАТОПЛЕНИЯ');
    expect(page2?.textContent).toContain('4. РАСПРЕДЕЛЕНИЕ ПО ТИПАМ ПОКРОВА');

    // Check print break before page 2
    expect((page2 as HTMLElement)?.style.breakBefore || (page2 as HTMLElement)?.className).toMatch(
      /page|break/i
    );
  });

  it('renders the scientific verification, crypto-audit, and ESG metrics section', () => {
    const reportWithAnalytics: ReportData = {
      ...mockReport,
      uncertainty: {
        pair_id: mockReport.pair_id,
        area_ha: 2847.3,
        confidence_level: 0.95,
        lower_bound_ha: 2647.7,
        upper_bound_ha: 3046.9,
        margin_ha: 199.6,
        relative_uncertainty_pct: 7.01,
        sigma_effective_ha: 101.8,
        effective_n_pixels: 5.0,
        spatial_correlation: 0.2,
      },
      audit: {
        certificate_id: 'CERT-HYDRO-2026-BLAGOVESHCHENSK',
        pair_id: mockReport.pair_id,
        aoi_id: 'blagoveshchensk',
        merkle_root: '9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08',
        merkle_root_sha256: '9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08',
        status: 'verified',
        verified: true,
      },
      sar_analytics: {
        pair_id: mockReport.pair_id,
        water_fraction: 0.055,
        water_area_ha: 2847.3,
        mean_vv_db: -16.2,
        mean_vh_db: -22.8,
        mean_vh_vv_ratio: -6.6,
        radar_contrast_db: 9.4,
        cloud_penetration_verified: true,
        double_bounce_fraction: 0.038,
      },
      carbon_impact: {
        pair_id: mockReport.pair_id,
        flood_ha: 2847.3,
        biomass_loss_dry_matter_t: 24202.0,
        carbon_loss_tC: 11389.2,
        emissions_equivalent_tCO2e: 41760.4,
        cropland_loss_tC: 4270.0,
        forest_loss_tC: 7119.2,
        credit_potential: {
          is_available: true,
          status: 'verified',
          E_proj_tCO2e: 0,
          E_base_tCO2e: 1500,
          LK_tCO2e: 0,
          R_tCO2e: 1500,
          H_tCO2e: 100,
          UNC_deduction_rate: 0.0,
          R_adj_tCO2e: 1500,
          buffer_reserve_B_tCO2e: 150,
          Q_credits: 1350,
          fractional_remainder: 0,
          valuations_rub: { 500: 675000, 1500: 2025000, 4000: 5400000 },
          area_ha: 2847.3,
          delta_t_years: 1,
        },
        notes: 'IPCC default',
      },
      competition_score: {
        pair_id: mockReport.pair_id,
        q_flood: 0.9854,
        raster_flood_ha: 2847.3,
        csv_flood_ha: 2847.3,
        discrepancy_pct: 0.0,
        is_within_2_percent: true,
      },
    };

    render(
      <ReportDocument
        report={reportWithAnalytics}
        comparison={mockComparison}
        forPdf={true}
      />
    );

    expect(screen.getByText('НАУЧНАЯ ВЕРИФИКАЦИЯ, КРИПТО-АУДИТ И ESG-МЕТРИКИ')).toBeDefined();
    expect(screen.getByText(/IPCC TIER 1 & MERKLE SHA-256 COMPLIANT/)).toBeDefined();
    expect(screen.getByText(/Крипто-аудит/)).toBeDefined();
    expect(screen.getByText(/SAR Поляриметрия/)).toBeDefined();
    expect(screen.getByText(/Углерод & ESG/)).toBeDefined();
    expect(screen.getByText(/Точность сегментации по ТЗ/)).toBeDefined();
  });
});
