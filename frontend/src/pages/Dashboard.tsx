import React, { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { Topbar } from '../components/layout/Topbar';
import { Sidebar } from '../components/layout/Sidebar';
import { MapContainer } from '../components/map/MapContainer';
import { KpiCards } from '../components/analytics/KpiCards';
import { LandcoverChart } from '../components/analytics/LandcoverChart';
import { HydrographChart } from '../components/analytics/HydrographChart';
import { AuditCard } from '../components/analytics/AuditCard';
import { UncertaintyCard } from '../components/analytics/UncertaintyCard';
import { SarAnalyticsCard } from '../components/analytics/SarAnalyticsCard';
import { OfficialScoreCard } from '../components/analytics/OfficialScoreCard';
import { CarbonMetricsCard } from '../components/analytics/CarbonMetricsCard';
import { useUiStore } from '../store/uiStore';
import { apiClient } from '../api/client';
import type { Pair, ReportData, HydroAuditCertificate, FloodUncertainty, SARAnalytics } from '../types/domain';
import {
  AlertTriangle,
  ArrowRight,
  FileText,
  CheckCircle,
  Map as MapIcon,
  ListFilter,
  BarChart3,
  ArrowLeft,
  Loader2,
  ShieldAlert,
} from 'lucide-react';
import { downloadReportPdf } from '../lib/pdfExport';

export const Dashboard: React.FC = () => {
  const { pairId } = useParams<{ pairId?: string }>();
  const navigate = useNavigate();
  const { activePairId, setActivePairId } = useUiStore();

  const [pairs, setPairs] = useState<Pair[]>([]);
  const [currentReport, setCurrentReport] = useState<ReportData | null>(null);
  const [audit, setAudit] = useState<HydroAuditCertificate | null>(null);
  const [uncertainty, setUncertainty] = useState<FloodUncertainty | null>(null);
  const [sar, setSar] = useState<SARAnalytics | null>(null);
  const [loadingPairs, setLoadingPairs] = useState(true);
  const [loadingReport, setLoadingReport] = useState(false);
  const [reportUnavailable, setReportUnavailable] = useState(false);
  const [loadingExtra, setLoadingExtra] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [downloadSuccess, setDownloadSuccess] = useState<string | null>(null);
  const [isExportingPdf, setIsExportingPdf] = useState(false);

  // Вкладка адаптивного мобильного вида: 'map' | 'pairs' | 'analytics'
  const [mobileTab, setMobileTab] = useState<'map' | 'pairs' | 'analytics'>('map');

  // Синхронизация параметра маршрута со стором
  useEffect(() => {
    if (pairId && pairId !== activePairId) {
      setActivePairId(pairId);
    } else if (!pairId && activePairId) {
      navigate(`/dashboard/${activePairId}`, { replace: true });
    }
  }, [pairId, activePairId, setActivePairId, navigate]);

  // Загрузка пар при монтировании
  const loadPairs = async () => {
    try {
      setLoadingPairs(true);
      const data = await apiClient.fetchPairs();
      setPairs(data);
      if (data.length > 0 && !pairId) {
        setActivePairId(data[0].pair_id);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingPairs(false);
    }
  };

  useEffect(() => {
    loadPairs();
  }, []);

  // Загрузка отчёта и дополнительной аналитики при изменении activePairId
  useEffect(() => {
    if (!activePairId) return;

    let isMounted = true;
    setLoadingReport(true);
    setReportUnavailable(false);
    setLoadingExtra(true);
    apiClient
      .fetchReport(activePairId)
      .then((rep) => {
        if (!isMounted) return;
        setCurrentReport(rep);
        setReportUnavailable(rep === null);
      })
      .catch((e) => {
        console.error(e);
        if (isMounted) {
          setCurrentReport(null);
          setReportUnavailable(true);
        }
      })
      .finally(() => {
        if (isMounted) setLoadingReport(false);
      });

    Promise.all([
      apiClient.fetchAudit(activePairId).catch(() => null),
      apiClient.fetchUncertainty(activePairId).catch(() => null),
      apiClient.fetchSarAnalytics(activePairId).catch(() => null),
    ])
      .then(([auditRes, uncertRes, sarRes]) => {
        if (isMounted) {
          setAudit(auditRes);
          setUncertainty(uncertRes);
          setSar(sarRes);
        }
      })
      .catch(console.error)
      .finally(() => {
        if (isMounted) setLoadingExtra(false);
      });

    return () => {
      isMounted = false;
    };
  }, [activePairId]);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await loadPairs();
    if (activePairId) {
      const [rep, auditRes, uncertRes, sarRes] = await Promise.all([
        apiClient.fetchReport(activePairId).catch(() => null),
        apiClient.fetchAudit(activePairId).catch(() => null),
        apiClient.fetchUncertainty(activePairId).catch(() => null),
        apiClient.fetchSarAnalytics(activePairId).catch(() => null),
      ]);
      setCurrentReport(rep);
      setReportUnavailable(rep === null);
      setAudit(auditRes);
      setUncertainty(uncertRes);
      setSar(sarRes);
    }
    setIsRefreshing(false);
  };

  const currentPair = pairs.find((p) => p.pair_id === activePairId) || null;

  // Обработчики экспорта
  const handleExportCsv = () => {
    if (!currentReport) return;
    const csvContent = [
      'metric,value,unit',
      `pair_id,${currentReport.pair_id},`,
      `event_name,"${currentReport.event_name}",`,
      `aoi_name,"${currentReport.aoi_name}",`,
      `flood_ha,${currentReport.flood_ha},ha`,
      `flood_km2,${currentReport.flood_km2},km2`,
      `water_pre_ha,${currentReport.water_pre_ha},ha`,
      `water_peak_ha,${currentReport.water_peak_ha},ha`,
      `receded_ha,${currentReport.receded_ha || 0},ha`,
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `report_${activePairId}.csv`;
    link.click();
    URL.revokeObjectURL(url);
    showNotice('CSV скачан');
  };

  const handleExportGeoJson = async () => {
    try {
      const gj = await apiClient.fetchLayerGeoJson(activePairId, 'flood');
      const blob = new Blob([JSON.stringify(gj || { type: 'FeatureCollection', features: [] }, null, 2)], {
        type: 'application/geo+json',
      });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `flood_layer_${activePairId}.geojson`;
      link.click();
      URL.revokeObjectURL(url);
      showNotice('GeoJSON скачан');
    } catch {
      showNotice('Ошибка экспорта GeoJSON');
    }
  };

  const handleExportShp = () => {
    // Официальный эндпоинт экспорта ESRI Shapefile (.shp, .shx, .dbf, .prj)
    window.open(`/api/v1/export/${encodeURIComponent(activePairId)}/shapefile?layer=flood`, '_blank');
    showNotice('SHP архив скачивается');
  };

  const handleMchsDispatch = () => {
    // Официальное экстренное полевое донесение МЧС
    window.open(`/api/v1/report/${encodeURIComponent(activePairId)}/mchs-dispatch?format=html`, '_blank');
    showNotice('Донесение МЧС сформировано');
  };

  const handleExportPdf = async () => {
    let rep = currentReport;
    if (!rep && activePairId) {
      try {
        rep = await apiClient.fetchReport(activePairId);
      } catch (e) {
        console.error(e);
      }
    }
    if (rep) {
      setIsExportingPdf(true);
      try {
        await downloadReportPdf(rep);
        showNotice('PDF копия отчёта успешно сохранена');
      } catch (err) {
        console.error(err);
        showNotice('Ошибка экспорта PDF');
      } finally {
        setIsExportingPdf(false);
      }
    }
  };

  const showNotice = (msg: string) => {
    setDownloadSuccess(msg);
    setTimeout(() => setDownloadSuccess(null), 2500);
  };

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-background text-text-primary font-sans">
      {/* Topbar */}
      <Topbar onRefresh={handleRefresh} isRefreshing={isRefreshing} />

      {/* Main Layout */}
      <div className="flex-1 flex overflow-hidden relative">
        {/* Left Sidebar: Events / Pairs */}
        <div
          className={`h-full shrink-0 z-20 transition-all duration-200 ${
            mobileTab === 'pairs'
              ? 'flex w-full absolute inset-0 bg-white z-40'
              : 'hidden lg:flex'
          }`}
        >
          {/* Mobile Back Button when opened in full screen */}
          {mobileTab === 'pairs' && (
            <div className="absolute top-3 right-3 z-30 lg:hidden">
              <button
                onClick={() => setMobileTab('map')}
                className="px-3 py-1.5 bg-slate-900 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 shadow-md"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                <span>К карте</span>
              </button>
            </div>
          )}
          <Sidebar
            pairs={pairs}
            isLoading={loadingPairs}
            onSelectPair={() => setMobileTab('map')}
          />
        </div>

        {/* Center: Leaflet Interactive Map */}
        <div
          className={`flex-1 relative h-full ${
            mobileTab === 'map' ? 'flex' : 'hidden lg:flex'
          }`}
        >
          <MapContainer currentPair={currentPair} />

          {/* Floating Mobile Controls overlayed on Map */}
          <div className="lg:hidden absolute top-3 left-3 right-3 flex items-center justify-between pointer-events-none z-[1000]">
            <button
              onClick={() => setMobileTab('pairs')}
              className="pointer-events-auto bg-white/95 backdrop-blur-sm border border-[#EAECF0] rounded-lg px-2.5 py-1.5 shadow-floating text-xs font-semibold text-text-primary flex items-center gap-1.5"
            >
              <ListFilter className="w-3.5 h-3.5 text-[#0EA5E9]" />
              <span className="truncate max-w-[130px]">
                {currentPair?.aoi_name || 'События'}
              </span>
            </button>

            <button
              onClick={() => setMobileTab('analytics')}
              className="pointer-events-auto bg-[#0EA5E9] text-white rounded-lg px-2.5 py-1.5 shadow-floating text-xs font-semibold flex items-center gap-1.5"
            >
              <BarChart3 className="w-3.5 h-3.5" />
              <span>Аналитика</span>
            </button>
          </div>
        </div>

        {/* Right Sidebar: Analytics */}
        <aside
          className={`bg-surface border-l border-border flex flex-col h-full overflow-y-auto shrink-0 p-4 space-y-4 z-20 ${
            mobileTab === 'analytics'
              ? 'flex w-full absolute inset-0 bg-white z-40'
              : 'hidden xl:flex w-96'
          }`}
        >
          {/* Mobile Back Button */}
          {mobileTab === 'analytics' && (
            <div className="flex items-center justify-between pb-2 border-b border-border xl:hidden">
              <button
                onClick={() => setMobileTab('map')}
                className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-text-primary rounded-lg text-xs font-semibold flex items-center gap-1.5"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                <span>Назад к карте</span>
              </button>
              <span className="text-xs font-bold text-text-secondary">Аналитическая панель</span>
            </div>
          )}

          {/* Header */}
          <div className="space-y-1">
            <h2 className="text-lg sm:text-xl font-bold text-text-primary tracking-tight truncate">
              {currentPair?.event_id || 'flood_2019_07'}
            </h2>
            <div className="text-xs text-text-secondary truncate">
              {currentPair
                ? `${currentPair.date_pre_sar || '12.07.2019'} -> ${currentPair.date_peak_sar || '14.07.2019'} · ${currentPair.aoi_name}`
                : '12.07.2019 -> 14.07.2019 · Благовещенск'}
            </div>
          </div>

          {/* Download Notification */}
          {downloadSuccess && (
            <div className="flex items-center gap-1.5 text-xs text-emerald-700 bg-emerald-50 px-3 py-2 rounded-lg border border-emerald-200 animate-in fade-in">
              <CheckCircle className="w-4 h-4" />
              <span>{downloadSuccess}</span>
            </div>
          )}

          {/* Report unavailable: never fall back to invented numbers */}
          {reportUnavailable && !loadingReport && (
            <div className="flex items-center gap-1.5 text-xs text-amber-800 bg-amber-50 px-3 py-2 rounded-lg border border-amber-200">
              <AlertTriangle className="w-4 h-4" />
              <span>Отчёт недоступен: сервис не вернул данные</span>
            </div>
          )}

          {/* KPI Cards */}
          <KpiCards report={currentReport} isLoading={loadingReport || reportUnavailable} />

          {/* Landcover Chart */}
          <LandcoverChart landcover={currentReport?.landcover} />

          {/* Hydrograph Mini Chart */}
          <HydrographChart
            datePre={currentPair?.date_pre_sar}
            datePeak={currentPair?.date_peak_sar}
            waterPreHa={currentReport?.water_pre_ha}
            waterPeakHa={currentReport?.water_peak_ha}
          />

          {/* Advanced Analytics & Official Competition Score */}
          <OfficialScoreCard activePairId={activePairId} isLoading={loadingReport} />
          <UncertaintyCard uncertainty={uncertainty} isLoading={loadingExtra} />
          <SarAnalyticsCard sar={sar} isLoading={loadingExtra} />
          <CarbonMetricsCard pairId={activePairId} isLoading={loadingReport} />
          <AuditCard audit={audit} isLoading={loadingExtra} />

          {/* Action Buttons */}
          <div className="space-y-2 pt-1">
            {/* MCHS Emergency Field Report Card */}
            <div className="p-3 bg-gradient-to-r from-red-50 to-orange-50 rounded-xl border border-red-200 space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5 text-xs font-bold text-red-900">
                  <ShieldAlert className="w-4 h-4 text-red-600" />
                  <span>Оперативное донесение МЧС</span>
                </div>
                <span className="text-[10px] uppercase font-bold tracking-wider px-1.5 py-0.5 rounded bg-red-100 text-red-700">
                  1/ЧС
                </span>
              </div>
              <p className="text-[11px] text-slate-600 leading-snug">
                Официальная сводка ЦУКС: затронутая застройка, сельхозугодья, отрезанные дороги и зонирование глубин.
              </p>
              <button
                onClick={handleMchsDispatch}
                className="w-full bg-red-600 hover:bg-red-700 text-white text-xs font-semibold py-2 rounded-lg transition-colors shadow-xs flex items-center justify-center gap-1.5 cursor-pointer"
                title="Сформировать и скачать официальное донесение МЧС России"
              >
                <ShieldAlert className="w-3.5 h-3.5" />
                <span>Скачать донесение МЧС</span>
              </button>
            </div>

            <button
              onClick={handleExportPdf}
              disabled={isExportingPdf}
              className="w-full bg-[#0EA5E9] hover:bg-[#0284C7] text-white text-xs font-semibold py-2.5 rounded-xl transition-colors shadow-xs flex items-center justify-center gap-2 cursor-pointer disabled:opacity-60"
            >
              {isExportingPdf ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <FileText className="w-4 h-4" />
              )}
              <span>{isExportingPdf ? 'Создание PDF...' : 'Скачать отчёт (PDF)'}</span>
            </button>

            <div className="grid grid-cols-3 gap-2">
              <button
                onClick={handleExportGeoJson}
                className="py-1.5 px-2 bg-white hover:bg-[#F8FAFC] border border-[#EAECF0] text-text-secondary hover:text-text-primary text-xs font-medium rounded-lg transition-colors flex items-center justify-center gap-1 shadow-2xs"
              >
                <span>GeoJSON</span>
              </button>
              <button
                onClick={handleExportShp}
                className="py-1.5 px-2 bg-white hover:bg-[#F8FAFC] border border-[#EAECF0] text-text-secondary hover:text-text-primary text-xs font-medium rounded-lg transition-colors flex items-center justify-center gap-1 shadow-2xs"
              >
                <span>SHP</span>
              </button>
              <button
                onClick={handleExportCsv}
                className="py-1.5 px-2 bg-white hover:bg-[#F8FAFC] border border-[#EAECF0] text-text-secondary hover:text-text-primary text-xs font-medium rounded-lg transition-colors flex items-center justify-center gap-1 shadow-2xs"
              >
                <span>CSV</span>
              </button>
            </div>

            <div className="pt-2 text-center">
              <Link
                to="/methodology#metric"
                className="inline-flex items-center gap-1 text-xs text-[#0EA5E9] hover:text-[#0284C7] font-medium transition-colors"
              >
                <span>Как считается метрика</span>
                <ArrowRight className="w-3 h-3" />
              </Link>
            </div>
          </div>
        </aside>
      </div>

      {/* Mobile Bottom Navigation Bar (Tabs) */}
      <nav className="lg:hidden h-12 bg-white border-t border-border flex items-center justify-around z-30 shrink-0 select-none">
        <button
          onClick={() => setMobileTab('map')}
          className={`flex-1 h-full flex flex-col items-center justify-center gap-0.5 text-[10px] font-medium transition-colors ${
            mobileTab === 'map'
              ? 'text-[#0EA5E9] font-bold'
              : 'text-text-secondary hover:text-text-primary'
          }`}
        >
          <MapIcon className="w-4 h-4" />
          <span>Карта</span>
        </button>

        <button
          onClick={() => setMobileTab('pairs')}
          className={`flex-1 h-full flex flex-col items-center justify-center gap-0.5 text-[10px] font-medium transition-colors ${
            mobileTab === 'pairs'
              ? 'text-[#0EA5E9] font-bold'
              : 'text-text-secondary hover:text-text-primary'
          }`}
        >
          <div className="relative">
            <ListFilter className="w-4 h-4" />
            {pairs.length > 0 && (
              <span className="absolute -top-1 -right-2 bg-[#0EA5E9] text-white text-[8px] font-bold px-1 rounded-full">
                {pairs.length}
              </span>
            )}
          </div>
          <span>Наблюдения</span>
        </button>

        <button
          onClick={() => setMobileTab('analytics')}
          className={`flex-1 h-full flex flex-col items-center justify-center gap-0.5 text-[10px] font-medium transition-colors ${
            mobileTab === 'analytics'
              ? 'text-[#0EA5E9] font-bold'
              : 'text-text-secondary hover:text-text-primary'
          }`}
        >
          <BarChart3 className="w-4 h-4" />
          <span>Аналитика</span>
        </button>
      </nav>

      {/* Bottom Status Bar (Desktop) */}
      <footer className="hidden lg:flex h-7 bg-white border-t border-border px-4 items-center justify-between text-[11px] text-text-muted shrink-0 select-none z-30">
        <div>Последнее обновление: {currentReport?.generated_at ? new Date(currentReport.generated_at).toLocaleString('ru-RU') : '—'}</div>
        <div className="hidden sm:block">
          Событие: {currentPair?.event_name || '—'}
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-emerald-500 inline-block animate-pulse" />
          <span className="text-text-secondary font-medium">API: online</span>
        </div>
      </footer>
    </div>
  );
};
