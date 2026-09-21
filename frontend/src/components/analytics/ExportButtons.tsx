import React from 'react';
import { Link } from 'react-router-dom';
import { FileText, Download } from 'lucide-react';
import { downloadReportPdf } from '../../lib/pdfExport';
import { apiClient } from '../../api/client';
import type { ReportData } from '../../types/domain';

interface ExportButtonsProps {
  pairId: string;
  report?: ReportData | null;
}

export const ExportButtons: React.FC<ExportButtonsProps> = ({ pairId, report }) => {
  const [downloadingPdf, setDownloadingPdf] = React.useState(false);

  const handleDownloadPdf = async () => {
    setDownloadingPdf(true);
    try {
      const data = report ?? (await apiClient.fetchReport(pairId));
      // Без серверного отчёта экспортировать достоверно нечего.
      if (!data) {
        console.error(`No report available for ${pairId}; PDF export skipped`);
        return;
      }
      downloadReportPdf(data);
    } catch (e) {
      console.error('Error generating PDF:', e);
    } finally {
      setDownloadingPdf(false);
    }
  };

  const downloadCsv = () => {
    window.open(`/api/v1/report/${encodeURIComponent(pairId)}/csv`, '_blank');
  };

  const downloadGeoJson = () => {
    window.open(`/api/v1/geojson/${encodeURIComponent(pairId)}?layer=flood`, '_blank');
  };

  // Экспорт SHP: реальный эндпоинт Shapefile (.zip); при недоступности откат к GeoJSON
  const downloadShp = () => {
    window.open(`/api/v1/export/${encodeURIComponent(pairId)}/vectors?format=shp`, '_blank');
  };

  return (
    <div className="space-y-2 pt-2">
      {/* Primary Action Button */}
      <button
        onClick={handleDownloadPdf}
        disabled={downloadingPdf}
        className="w-full py-2.5 px-4 bg-accent hover:bg-accent-hover text-white rounded-xl text-xs font-semibold flex items-center justify-center gap-2 shadow-sm transition-all disabled:opacity-75"
      >
        <FileText className="w-4 h-4" />
        <span>{downloadingPdf ? 'Генерация PDF...' : 'Скачать отчёт (PDF)'}</span>
      </button>

      {/* Row of Secondary Export Buttons */}
      <div className="grid grid-cols-3 gap-2">
        <button
          onClick={downloadGeoJson}
          className="py-1.5 px-2 bg-surface hover:bg-[#F8FAFC] border border-border rounded-lg text-xs font-medium text-text-secondary hover:text-text-primary transition-all text-center flex items-center justify-center gap-1"
        >
          <Download className="w-3 h-3 text-text-muted" />
          <span>GeoJSON</span>
        </button>

        <button
          onClick={downloadShp}
          className="py-1.5 px-2 bg-surface hover:bg-[#F8FAFC] border border-border rounded-lg text-xs font-medium text-text-secondary hover:text-text-primary transition-all text-center flex items-center justify-center gap-1"
        >
          <Download className="w-3 h-3 text-text-muted" />
          <span>SHP</span>
        </button>

        <button
          onClick={downloadCsv}
          className="py-1.5 px-2 bg-surface hover:bg-[#F8FAFC] border border-border rounded-lg text-xs font-medium text-text-secondary hover:text-text-primary transition-all text-center flex items-center justify-center gap-1"
        >
          <Download className="w-3 h-3 text-text-muted" />
          <span>CSV</span>
        </button>
      </div>

      <div className="text-center pt-1">
        <Link
          to="/methodology"
          className="text-xs text-accent hover:text-accent-hover font-medium inline-flex items-center gap-1"
        >
          <span>Как считается метрика</span>
          <span>{'->'}</span>
        </Link>
      </div>
    </div>
  );
};
