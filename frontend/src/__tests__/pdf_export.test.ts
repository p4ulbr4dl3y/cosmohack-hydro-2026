// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { downloadReportPdf } from '../lib/pdfExport';
import type { ReportData } from '../types/domain';

// Мок getContext и toDataURL у canvas в jsdom
beforeEach(() => {
  HTMLCanvasElement.prototype.getContext = vi.fn().mockReturnValue({
    fillRect: vi.fn(),
    drawImage: vi.fn(),
  }) as any;
  HTMLCanvasElement.prototype.toDataURL = vi.fn().mockReturnValue('data:image/jpeg;base64,mock');
});

// Мок html2canvas
vi.mock('html2canvas', () => {
  return {
    default: vi.fn().mockImplementation(() => {
      const canvas = document.createElement('canvas');
      canvas.width = 1000;
      canvas.height = 1400;
      return Promise.resolve(canvas);
    }),
  };
});

// Мок jsPDF
const saveMock = vi.fn();
const addImageMock = vi.fn();
const addPageMock = vi.fn();

vi.mock('jspdf', () => {
  return {
    jsPDF: vi.fn().mockImplementation(() => ({
      save: saveMock,
      addImage: addImageMock,
      addPage: addPageMock,
      setFontSize: vi.fn(),
      text: vi.fn(),
    })),
  };
});

const mockReport: ReportData = {
  pair_id: 'flood_2019_07_amur__blagoveshchensk',
  event_id: 'flood_2019_07_amur',
  event_name: 'Паводок в Приамурье, июль 2019',
  aoi_id: 'blagoveshchensk',
  aoi_name: 'Благовещенск',
  year: 2019,
  date_pre_sar: '2019-06-13',
  date_peak_sar: '2019-07-25',
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
};

describe('downloadReportPdf', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('successfully generates and downloads a PDF for the given report', async () => {
    await downloadReportPdf(mockReport);

    expect(saveMock).toHaveBeenCalledWith('report_flood_2019_07_amur__blagoveshchensk.pdf');
    expect(addImageMock).toHaveBeenCalled();
  });

  it('handles existing DOM printable area if already mounted', async () => {
    const existing = document.createElement('div');
    existing.id = 'report-printable-area';
    existing.innerText = 'Pre-rendered report';
    document.body.appendChild(existing);

    await downloadReportPdf(mockReport);

    expect(saveMock).toHaveBeenCalledWith('report_flood_2019_07_amur__blagoveshchensk.pdf');
    document.body.removeChild(existing);
  });

  it('falls back gracefully if html2canvas throws an error', async () => {
    const html2canvas = (await import('html2canvas')).default;
    vi.mocked(html2canvas).mockRejectedValueOnce(new Error('Canvas error'));

    await downloadReportPdf(mockReport);

    expect(saveMock).toHaveBeenCalledWith('report_flood_2019_07_amur__blagoveshchensk.pdf');
  });

  it('renders discrete pages and triggers addPage when data-pdf-page attributes are present', async () => {
    const existing = document.createElement('div');
    existing.id = 'report-printable-area';
    const page1 = document.createElement('div');
    page1.setAttribute('data-pdf-page', '1');
    const page2 = document.createElement('div');
    page2.setAttribute('data-pdf-page', '2');
    existing.appendChild(page1);
    existing.appendChild(page2);
    document.body.appendChild(existing);

    await downloadReportPdf(mockReport);

    expect(addPageMock).toHaveBeenCalledTimes(1); // 2 страницы всего = 1 вызов addPage()
    expect(addImageMock).toHaveBeenCalledTimes(2);
    expect(saveMock).toHaveBeenCalledWith('report_flood_2019_07_amur__blagoveshchensk.pdf');
    document.body.removeChild(existing);
  });
});
