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

    expect(screen.getByText('HydroWatch')).toBeDefined();
    expect(screen.getAllByText('Паводок в Приамурье, июль 2019').length).toBeGreaterThan(0);
    expect(screen.getByText(/КосмоХакатон 2026/)).toBeDefined();
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
    expect(screen.getByText('2019-06-18 -> 2019-07-30')).toBeDefined();
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

    // Проверка, что числовые текстовые узлы отрисованы
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
    expect(screen.getByText(/Данные Copernicus © ESA/)).toBeDefined();
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

    // Разделы 1 и 2 на странице 1
    expect(page1?.textContent).toContain('1. ИСХОДНЫЕ ДАННЫЕ');
    expect(page1?.textContent).toContain('2. РЕЗУЛЬТАТЫ ГИДРОЛОГИЧЕСКОГО АНАЛИЗА');

    // Раздел 3 (карта) и раздел 4 на странице 2
    expect(page2?.textContent).toContain('3. КАРТА ЗАТОПЛЕНИЯ');
    expect(page2?.textContent).toContain('4. РАСПРЕДЕЛЕНИЕ ПО ТИПАМ ПОКРОВА');

    // Проверка разрыва печати перед страницей 2
    expect((page2 as HTMLElement)?.style.breakBefore || (page2 as HTMLElement)?.className).toMatch(
      /page|break/i
    );
  });
});
