import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { apiClient } from '../api/client';
import type { ReportData, ComparisonData } from '../types/domain';
import { downloadReportPdf } from '../lib/pdfExport';
import { ReportDocument } from '../components/report/ReportDocument';
import {
  ArrowLeft,
  FileText,
  Printer,
  Download,
  CheckCircle,
  Loader2,
} from 'lucide-react';

export const Report: React.FC = () => {
  const { pairId = 'flood_2019_07_amur__blagoveshchensk' } = useParams<{ pairId: string }>();
  const navigate = useNavigate();

  const [report, setReport] = useState<ReportData | null>(null);
  const [comparison, setComparison] = useState<ComparisonData | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [exportNotice, setExportNotice] = useState<string | null>(null);
  const [isExportingPdf, setIsExportingPdf] = useState(false);

  useEffect(() => {
    let isMounted = true;
    setLoading(true);
    setLoadError(null);

    Promise.all([apiClient.fetchReport(pairId), apiClient.fetchComparison(pairId)])
      .then(([rep, comp]) => {
        if (!isMounted) return;
        setReport(rep);
        setComparison(comp);
        // A null report means the API returned no data; the spinner must stop
        // and the failure must be shown instead of hanging forever.
        if (!rep) {
          setLoadError('Отчёт недоступен: сервис не вернул данные для этой пары.');
        }
      })
      .catch((e) => {
        console.error(e);
        if (isMounted) setLoadError('Отчёт недоступен: не удалось связаться с сервисом.');
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [pairId]);

  const showNotice = (msg: string) => {
    setExportNotice(msg);
    setTimeout(() => setExportNotice(null), 3000);
  };

  const handlePrintPdf = async () => {
    if (!report) return;
    setIsExportingPdf(true);
    try {
      await downloadReportPdf(report, comparison);
      showNotice('PDF копия отчёта успешно сохранена');
    } catch (e) {
      console.error(e);
      showNotice('Ошибка экспорта PDF');
    } finally {
      setIsExportingPdf(false);
    }
  };

  const handleNativePrint = () => {
    window.print();
  };

  const handleExportJson = () => {
    if (!report) return;
    const blob = new Blob([JSON.stringify(report, null, 2)], {
      type: 'application/json',
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `report_${pairId}.json`;
    link.click();
    URL.revokeObjectURL(url);
    showNotice('JSON успешно скачан');
  };

  const handleExportCsv = () => {
    if (!report) return;
    const rows = [
      'metric,label,value,unit',
      `flood_ha,Новое затопление,${report.flood_ha},га`,
      `water_peak_ha,Водное зеркало (пик),${report.water_peak_ha},га`,
      `water_pre_ha,Водное зеркало (до),${report.water_pre_ha},га`,
      `receded_ha,Убыль воды,${report.receded_ha || 0},га`,
      `aoi_km2,Площадь района,${report.aoi_km2},км²`,
    ];
    const blob = new Blob([rows.join('\n')], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `report_${pairId}.csv`;
    link.click();
    URL.revokeObjectURL(url);
    showNotice('CSV успешно скачан');
  };

  const handleExportGeoJson = async () => {
    try {
      const data = await apiClient.fetchLayerGeoJson(pairId, 'flood');
      const blob = new Blob([JSON.stringify(data || { type: 'FeatureCollection', features: [] }, null, 2)], {
        type: 'application/geo+json',
      });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `flood_layer_${pairId}.geojson`;
      link.click();
      URL.revokeObjectURL(url);
      showNotice('GeoJSON успешно скачан');
    } catch {
      showNotice('Ошибка экспорта GeoJSON');
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#FAFBFC] flex items-center justify-center p-8">
        <div className="text-center space-y-3">
          <div className="w-10 h-10 border-3 border-[#0EA5E9] border-t-transparent rounded-full animate-spin mx-auto" />
          <div className="text-sm text-text-secondary font-medium">Генерация сводного отчёта...</div>
        </div>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="min-h-screen bg-[#FAFBFC] flex items-center justify-center p-8">
        <div className="max-w-md text-center space-y-4">
          <div className="text-base font-semibold text-text-primary">Отчёт недоступен</div>
          <div className="text-sm text-text-secondary">
            {loadError || 'Сервис не вернул данные отчёта для этой пары.'}
          </div>
          <button
            onClick={() => navigate(`/dashboard/${pairId}`)}
            className="inline-flex items-center gap-2 text-xs font-medium text-text-secondary hover:text-text-primary px-3 py-2 rounded-lg border border-[#EAECF0] bg-white hover:bg-slate-50 transition-colors shadow-2xs cursor-pointer"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Назад к дашборду</span>
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#FAFBFC] text-text-primary font-sans p-3 sm:p-6 md:p-10 print:p-0 print:bg-white">
      {/* Top Action Bar (hidden when printing) */}
      <div className="max-w-5xl mx-auto mb-6 flex flex-wrap items-center justify-between gap-3 print:hidden">
        <button
          onClick={() => navigate(`/dashboard/${pairId}`)}
          className="inline-flex items-center gap-2 text-xs font-medium text-text-secondary hover:text-text-primary px-3 py-2 rounded-lg border border-[#EAECF0] bg-white hover:bg-slate-50 transition-colors shadow-2xs cursor-pointer"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Назад к дашборду</span>
        </button>

        <div className="flex flex-wrap items-center gap-2">
          {exportNotice && (
            <div className="flex items-center gap-1.5 text-xs text-emerald-700 bg-emerald-50 px-3 py-1.5 rounded-lg border border-emerald-200">
              <CheckCircle className="w-4 h-4" />
              <span>{exportNotice}</span>
            </div>
          )}

          <button
            onClick={handlePrintPdf}
            disabled={isExportingPdf}
            className="px-3.5 py-2 bg-[#0EA5E9] hover:bg-[#0284C7] text-white text-xs font-semibold rounded-lg transition-colors flex items-center gap-1.5 shadow-xs disabled:opacity-60 cursor-pointer"
            title="Скачать точную копию отчёта в формате PDF"
          >
            {isExportingPdf ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <FileText className="w-4 h-4" />
            )}
            <span>{isExportingPdf ? 'Создание PDF...' : 'Скачать PDF'}</span>
          </button>

          <button
            onClick={handleNativePrint}
            className="px-3 py-2 border border-[#EAECF0] bg-white hover:bg-slate-50 text-text-primary text-xs font-medium rounded-lg transition-colors flex items-center gap-1.5 shadow-2xs cursor-pointer"
            title="Печать или сохранение через диалог браузера"
          >
            <Printer className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Печать</span>
          </button>

          <button
            onClick={handleExportCsv}
            className="px-3 py-2 border border-[#EAECF0] bg-white hover:bg-slate-50 text-text-primary text-xs font-medium rounded-lg transition-colors flex items-center gap-1 shadow-2xs cursor-pointer"
          >
            <Download className="w-3.5 h-3.5" />
            <span>CSV</span>
          </button>

          <button
            onClick={handleExportJson}
            className="px-3 py-2 border border-[#EAECF0] bg-white hover:bg-slate-50 text-text-primary text-xs font-medium rounded-lg transition-colors flex items-center gap-1 shadow-2xs cursor-pointer"
          >
            <Download className="w-3.5 h-3.5" />
            <span>JSON</span>
          </button>

          <button
            onClick={handleExportGeoJson}
            className="px-3 py-2 border border-[#EAECF0] bg-white hover:bg-slate-50 text-text-primary text-xs font-medium rounded-lg transition-colors flex items-center gap-1 shadow-2xs cursor-pointer"
          >
            <Download className="w-3.5 h-3.5" />
            <span>GeoJSON</span>
          </button>
        </div>
      </div>

      {/* Main Report Visual Component */}
      <ReportDocument report={report} comparison={comparison} />
    </div>
  );
};
