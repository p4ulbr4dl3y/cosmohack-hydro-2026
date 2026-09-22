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
  const [exportNotice, setExportNotice] = useState<string | null>(null);
  const [isExportingPdf, setIsExportingPdf] = useState(false);

  useEffect(() => {
    let isMounted = true;
    setLoading(true);

    Promise.all([
      apiClient.fetchReport(pairId),
      apiClient.fetchComparison(pairId),
      apiClient.fetchAudit(pairId).catch(() => null),
      apiClient.fetchUncertainty(pairId).catch(() => null),
      apiClient.fetchSarAnalytics(pairId).catch(() => null),
      apiClient.fetchCarbonImpact(pairId).catch(() => null),
      apiClient.fetchOfficialMetrics().catch(() => null),
    ])
      .then(([rep, comp, aud, unc, sar, carb, off]) => {
        if (isMounted) {
          const detail = off?.details?.find((d) => d.pair_id === pairId);
          const mergedReport: ReportData = {
            ...rep,
            audit: rep.audit || aud || undefined,
            uncertainty: rep.uncertainty || unc || undefined,
            sar_analytics: rep.sar_analytics || sar || undefined,
            carbon_impact: rep.carbon_impact || carb || undefined,
            competition_score: rep.competition_score || detail || undefined,
          };
          setReport(mergedReport);
          setComparison(comp);
        }
      })
      .catch(console.error)
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
    const unc = report.uncertainty;
    const aud = report.audit;
    const sar = report.sar_analytics;
    const carb = report.carbon_impact;
    const cred = carb?.credit_potential;
    const comp = report.competition_score;
    const lc = report.landcover || {};

    const rows = [
      'metric,label,value,unit',
      `pair_id,Идентификатор пары,${report.pair_id},id`,
      `aoi_name,Район наблюдения,${report.aoi_name},текст`,
      `event_name,Событие,${report.event_name},текст`,
      `date_pre_sar,Дата SAR до паводка,${report.date_pre_sar},дата`,
      `date_peak_sar,Дата SAR пика паводка,${report.date_peak_sar},дата`,
      `aoi_km2,Площадь района,${report.aoi_km2},км²`,
      `aoi_ha,Площадь района,${report.aoi_ha},га`,
      `flood_ha,Новое затопление,${report.flood_ha},га`,
      `water_peak_ha,Водное зеркало (пик),${report.water_peak_ha},га`,
      `water_pre_ha,Водное зеркало (до),${report.water_pre_ha},га`,
      `receded_ha,Убыль воды,${report.receded_ha || 0},га`,
      `water_gain_ha,Прирост водного зеркала,${report.water_gain_ha || 0},га`,
      `water_gain_pct,Относительный прирост воды,${report.water_gain_pct || 0},%`,
      `share_of_aoi,Доля затопления в AOI,${report.share_of_aoi || 0},доля`,
      `landcover_builtup_ha,Затопленная застройка,${lc.builtup_ha || 0},га`,
      `landcover_builtup_pct,Доля застройки,${lc.builtup_pct || 0},%`,
      `landcover_cropland_ha,Затопленные сельхозугодья,${lc.cropland_ha || 0},га`,
      `landcover_cropland_pct,Доля сельхозугодий,${lc.cropland_pct || 0},%`,
      `landcover_natural_ha,Затопленная растительность,${lc.natural_vegetation_ha || 0},га`,
      `landcover_natural_pct,Доля растительности,${lc.natural_vegetation_pct || 0},%`,
      `historic_water_ha,Исторический максимум воды GSW,${lc.historic_water_extent_ha || (lc as any).historic_water_ha || 0},га`,
      `mean_hand_m,Средняя относительная высота HAND,${lc.mean_hand_m || 0},м`,
      `uncertainty_ci_lower_ha,Нижняя граница ДИ 95%,${unc?.lower_bound_ha ?? ''},га`,
      `uncertainty_ci_upper_ha,Верхняя граница ДИ 95%,${unc?.upper_bound_ha ?? ''},га`,
      `uncertainty_margin_ha,Абсолютная погрешность ±,${unc?.margin_ha ?? ''},га`,
      `uncertainty_rel_pct,Относительная погрешность,${unc?.relative_uncertainty_pct ?? ''},%`,
      `uncertainty_effective_n,Эффективный объем выборки n_eff,${unc?.effective_n_pixels ?? ''},пикс`,
      `uncertainty_spatial_corr,Пространственная автокорреляция rho,${unc?.spatial_correlation ?? ''},коэф`,
      `merkle_root_sha256,Криптографический Merkle Root,${aud?.merkle_root ?? aud?.merkle_root_sha256 ?? ''},хеш`,
      `merkle_signature,ECDSA-подпись реестра,${aud?.signature_hash ?? ''},хеш`,
      `merkle_status,Статус криптографического аудита,${aud?.status ?? ''},статус`,
      `sar_mean_vv_db,Средний уровень SAR VV,${sar?.mean_vv_db ?? ''},дБ`,
      `sar_mean_vh_db,Средний уровень SAR VH,${sar?.mean_vh_db ?? ''},дБ`,
      `sar_contrast_db,Радарный контраст вода/суша,${sar?.radar_contrast_db ?? ''},дБ`,
      `biomass_loss_t,Потери сухой фитомассы,${carb?.biomass_loss_dry_matter_t ?? ''},т`,
      `carbon_loss_tC,Потери углеродного пула,${carb?.carbon_loss_tC ?? ''},т C`,
      `emissions_equivalent_tCO2e,Эквивалент выбросов парниковых газов,${carb?.emissions_equivalent_tCO2e ?? ''},т CO2e`,
      `carbon_credits_Q,Потенциал компенсационных квот Q,${cred?.Q_credits ?? ''},шт`,
      `buffer_reserve_B,Буферный углеродный резерв B,${cred?.buffer_reserve_B_tCO2e ?? (cred as any)?.buffer_reserve_B ?? ''},шт`,
      `competition_q_flood,Оценка точности Q_flood,${comp?.q_flood ?? ''},коэффициент`,
      `discrepancy_pct,Расхождение растр vs CSV,${comp?.discrepancy_pct ?? (comp as any)?.raster_csv_discrepancy_pct ?? ''},%`,
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

  const handleExportShp = async () => {
    try {
      showNotice('Подготовка SHP архива...');
      await apiClient.downloadShapefile(pairId, 'flood');
      showNotice('SHP архив успешно скачан');
    } catch (e) {
      console.error(e);
      showNotice('Ошибка экспорта SHP архива');
    }
  };

  if (loading || !report) {
    return (
      <div className="min-h-screen bg-[#FAFBFC] flex items-center justify-center p-8">
        <div className="text-center space-y-3">
          <div className="w-10 h-10 border-3 border-[#0EA5E9] border-t-transparent rounded-full animate-spin mx-auto" />
          <div className="text-sm text-text-secondary font-medium">Генерация сводного отчёта...</div>
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

          <button
            onClick={handleExportShp}
            className="px-3 py-2 border border-[#BAE6FD] bg-[#F0F9FF] hover:bg-[#E0F2FE] text-[#0284C7] text-xs font-semibold rounded-lg transition-colors flex items-center gap-1 shadow-2xs cursor-pointer"
            title="Скачать векторные слои в формате ESRI Shapefile (.zip)"
          >
            <Download className="w-3.5 h-3.5 text-[#0EA5E9]" />
            <span>SHP</span>
          </button>
        </div>
      </div>

      {/* Main Report Visual Component */}
      <ReportDocument report={report} comparison={comparison} />
    </div>
  );
};
