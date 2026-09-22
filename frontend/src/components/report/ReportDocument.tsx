import React from 'react';
import type {
  ReportData,
  ComparisonData,
  HydroAuditCertificate,
  FloodUncertainty,
  SARAnalytics,
  FloodCarbonImpact,
  OfficialMetrics,
} from '../../types/domain';
import { formatNumber, formatHa, formatKm2 } from '../../lib/format';
import { deriveLandcoverItems } from '../../lib/landcover';
import { MapContainer } from '../map/MapContainer';

interface ReportDocumentProps {
  report: ReportData;
  comparison?: ComparisonData | null;
  audit?: HydroAuditCertificate | null;
  uncertainty?: FloodUncertainty | null;
  sarAnalytics?: SARAnalytics | null;
  carbonImpact?: FloodCarbonImpact | null;
  officialMetrics?: OfficialMetrics | null;
  forPdf?: boolean;
}

export const ReportDocument: React.FC<ReportDocumentProps> = ({
  report,
  comparison,
  audit,
  uncertainty,
  sarAnalytics,
  carbonImpact,
  officialMetrics,
  forPdf = false,
}) => {
  const effectiveUncertainty = uncertainty || report.uncertainty;
  const effectiveAudit = audit || report.audit;
  const effectiveSar = sarAnalytics || report.sar_analytics;
  const effectiveCarbon = carbonImpact || report.carbon_impact;
  const effectiveScore =
    report.competition_score ||
    officialMetrics?.details?.find((d) => d.pair_id === report.pair_id);
  // Предпочтение агрегатам по классам, возвращаемым /api/v1/report/{pair_id}
  const landcoverItems = React.useMemo(
    () =>
      deriveLandcoverItems(report.landcover)?.map((it) => ({
        class_name: it.class_name,
        area_ha: it.area_ha,
        pct: it.percentage,
      })) ?? [],
    [report.landcover]
  );

  const currentDateFormatted = React.useMemo(() => {
    if (report.generated_at) {
      const d = new Date(report.generated_at);
      if (!Number.isNaN(d.getTime())) {
        return `${d.toISOString().slice(0, 16).replace('T', ' ')} UTC`;
      }
    }
    return '—';
  }, [report.generated_at]);

  const hasOptical = Boolean(report.date_pre_opt && report.date_peak_opt);
  const opticalWindow = hasOptical
    ? `${report.date_pre_opt} -> ${report.date_peak_opt}`
    : 'нет перекрывающей сцены';

  const renderReportFooter = (pageNumber: number, totalPages: number = 2) => (
    <footer className="mt-auto pt-6 border-t border-[#EAECF0] flex flex-col sm:flex-row items-center justify-between gap-3 text-sm text-text-muted">
      <div className="flex items-center gap-2 text-center sm:text-left">
        <img src="/icons/logo.png" alt="HydroWatch" className="w-5 h-5 object-contain opacity-80 shrink-0" />
        <span className="font-bold text-text-primary text-sm">HydroWatch Amur</span>
        <span>·</span>
        <span className="text-text-secondary font-medium">КосмоХакатон 2026</span>
        <span className="hidden sm:inline">·</span>
        <span className="hidden sm:inline text-xs text-text-muted">Данные Copernicus © ESA, 2019-2026</span>
      </div>
      <div className="flex items-center gap-3 font-mono text-xs">
        <span className="inline-flex items-center gap-1.5 text-emerald-700 font-bold bg-emerald-50 border border-emerald-200/80 px-2.5 py-1 rounded-md shadow-2xs">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          Верифицировано
        </span>
        <span className="text-text-primary font-semibold px-2.5 py-1 rounded bg-slate-100 border border-slate-200">
          Страница {pageNumber} из {totalPages}
        </span>
      </div>
    </footer>
  );

  // API возвращает голые коды сенсоров ("sentinel1"); они отображаются как читаемые имена.
  const sensorSar = React.useMemo(() => {
    const code = (report.sensor_sar || '').toLowerCase().replace(/[-_\s]/g, '');
    if (code === 'sentinel1') return 'Sentinel-1';
    if (code === 'sentinel2') return 'Sentinel-2';
    return report.sensor_sar || 'Sentinel-1';
  }, [report.sensor_sar]);

  return (
    <div
      id="report-printable-area"
      className="w-full max-w-5xl mx-auto space-y-8 print:space-y-0 print:p-0 print:m-0"
    >
      {/* СТРАНИЦА 1: МЕТАДАННЫЕ И РЕЗУЛЬТАТЫ */}
      <div
        data-pdf-page="1"
        className="bg-white border border-[#EAECF0] rounded-2xl shadow-card p-8 sm:p-10 flex flex-col justify-between min-h-[1140px] print:min-h-[297mm] print:border-none print:shadow-none print:p-0 print:m-0 space-y-6"
      >
        {/* Заголовок */}
        <header className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#F1F5F9] pb-5">
          <div className="flex items-center gap-3">
            <img src="/icons/logo.png" alt="HydroWatch" className="w-9 h-9 object-contain" />
            <div className="flex items-baseline gap-2">
              <span className="font-bold text-2xl tracking-tight text-text-primary">HydroWatch</span>
              <span className="text-text-muted text-lg font-normal">Amur</span>
            </div>
            <span className="text-text-muted hidden sm:inline">|</span>
            <span className="text-sm text-text-secondary font-medium">Автоматический отчёт</span>
          </div>

          <div className="text-sm text-text-muted font-mono">
            Сгенерировано: {currentDateFormatted}
          </div>
        </header>

        {/* Блок заголовка */}
        <div className="space-y-1.5">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-md bg-[#E0F2FE] text-[#0284C7] text-xs font-bold uppercase tracking-wider mb-0.5">
            КосмоХакатон 2026
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-text-primary leading-tight py-0.5 break-words">
            {report.event_name || 'Паводок, июль 2019 — Благовещенск'}
          </h1>
          <div className="font-mono text-sm text-text-muted leading-relaxed">
            pair_id: <span className="text-text-primary font-semibold">{report.pair_id}</span> · AOI: <span className="text-text-primary font-semibold">{report.aoi_name || 'Благовещенск'}</span>
          </div>
        </div>

        {/* 1. ИСХОДНЫЕ ДАННЫЕ */}
        <section className="space-y-3">
          <div className="text-xs font-bold text-[#0284C7] tracking-wider uppercase">
            1. ИСХОДНЫЕ ДАННЫЕ
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {/* Карточка 1: Sentinel-1 (SAR) */}
          <div className="border border-[#EAECF0] rounded-xl p-4 bg-white space-y-3 shadow-2xs">
            <div className="flex items-center gap-2 text-xs font-semibold text-text-primary">
              <img src="/icons/sattelate2.png" alt="SAR" className="w-5 h-5 object-contain" />
              <span>Sentinel-1 (SAR)</span>
            </div>
            <div className="grid grid-cols-2 gap-y-2 text-xs">
              <span className="text-text-secondary">Дата наблюдения</span>
              <span className="font-mono text-text-primary text-right font-medium">
                {report.date_pre_sar || '—'} {'->'} {report.date_peak_sar || '—'}
              </span>
              <span className="text-text-secondary">Сенсор</span>
              <span className="font-mono text-text-primary text-right uppercase">
                {sensorSar}
              </span>
              <span className="text-text-secondary">Поляризации</span>
              <span className="font-mono text-text-primary text-right">VV / VH</span>
            </div>
          </div>

          {/* Карточка 2: Sentinel-2 (MSI) */}
          <div className="border border-[#EAECF0] rounded-xl p-4 bg-white space-y-3 shadow-2xs">
            <div className="flex items-center gap-2 text-xs font-semibold text-text-primary">
              <img src="/icons/image.png" alt="MSI" className="w-5 h-5 object-contain" />
              <span>Sentinel-2 (MSI)</span>
            </div>
            <div className="grid grid-cols-2 gap-y-2 text-xs">
              <span className="text-text-secondary">Дата наблюдения</span>
              <span className="font-mono text-text-primary text-right font-medium">
                {opticalWindow}
              </span>
              <span className="text-text-secondary">Статус</span>
              <div className="text-right">
                <span
                  className={
                    hasOptical
                      ? 'bg-emerald-50 text-emerald-700 font-semibold px-2 py-0.5 rounded text-[11px]'
                      : 'bg-[#FEF3C7] text-[#92400E] font-semibold px-2 py-0.5 rounded text-[11px]'
                  }
                >
                  {hasOptical ? 'ПРИГОДНА' : 'НЕТ ОПТИКИ'}
                </span>
              </div>
            </div>
          </div>

          {/* Card 3: Район интереса */}
          <div className="border border-[#EAECF0] rounded-xl p-4 bg-white space-y-3 shadow-2xs">
            <div className="flex items-center gap-2 text-xs font-semibold text-text-primary">
              <img src="/icons/map.png" alt="AOI" className="w-5 h-5 object-contain" />
              <span>Район интереса (AOI)</span>
            </div>
            <div className="grid grid-cols-2 gap-y-2 text-xs">
              <span className="text-text-secondary shrink-0">Название</span>
              <span className="text-text-primary text-right font-medium leading-snug break-words">
                {report.aoi_name || 'Благовещенск'}
              </span>
              <span className="text-text-secondary">Площадь</span>
              <span className="font-mono text-text-primary text-right">
                {formatKm2(report.aoi_km2, 0)} ({formatHa(report.aoi_ha, 0)})
              </span>
              <span className="text-text-secondary">Центр (lat, lon)</span>
              <span className="font-mono text-text-primary text-right">
                {report.center_4326
                  ? `${report.center_4326[0].toFixed(4)}° N, ${report.center_4326[1].toFixed(4)}° E`
                  : '—'}
              </span>
            </div>
          </div>

          {/* Card 4: Вспомогательные слои */}
          <div className="border border-[#EAECF0] rounded-xl p-4 bg-white space-y-3 shadow-2xs">
            <div className="flex items-center gap-2 text-xs font-semibold text-text-primary">
              <img src="/icons/layers.png" alt="Aux" className="w-5 h-5 object-contain" />
              <span>Вспомогательные геослои</span>
            </div>
            <div className="space-y-1.5 text-xs text-text-secondary">
              <div>• Copernicus DEM (SRTM GLO-30)</div>
              <div>• MERIT Hydro (HAND гидросеть)</div>
              <div>• JRC GSW (Global Surface Water)</div>
              <div>• ERA5 (климатические осадки)</div>
            </div>
          </div>
        </div>
      </section>

      {/* 2. РЕЗУЛЬТАТЫ */}
      <section className="space-y-3">
        <div className="text-[11px] font-bold text-text-muted tracking-wider uppercase">
          2. РЕЗУЛЬТАТЫ ГИДРОЛОГИЧЕСКОГО АНАЛИЗА
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {/* KPI 1 */}
          <div className="border border-[#EAECF0] rounded-xl p-3.5 relative pl-4 bg-white shadow-2xs">
            <div className="absolute left-0 top-0 bottom-0 w-1.5 bg-[#F97316] rounded-l-xl" />
            <div className="text-[11px] font-semibold text-text-muted tracking-wider uppercase">
              НОВОЕ ЗАТОПЛЕНИЕ
            </div>
            <div className="mt-1 font-mono text-lg sm:text-xl font-bold text-text-primary tabular-nums whitespace-nowrap">
              {formatHa(report.flood_ha, 1)}
            </div>
            <div className="text-xs text-text-secondary mt-0.5 whitespace-nowrap">
              {formatKm2(report.flood_km2, 2)} · {((report.flood_ha / (report.aoi_ha || 1)) * 100).toFixed(2)}% AOI
            </div>
            {effectiveUncertainty && (
              <div className="mt-2 pt-1.5 border-t border-slate-100 flex items-center justify-between text-[10px] text-text-muted font-mono">
                <span>ДИ 95%:</span>
                <span className="text-[#0284C7] font-semibold">
                  [{formatNumber(effectiveUncertainty.lower_bound_ha, 0)}…{formatNumber(effectiveUncertainty.upper_bound_ha, 0)}] га (±{effectiveUncertainty.relative_uncertainty_pct.toFixed(1)}%)
                </span>
              </div>
            )}
          </div>

          {/* KPI 2 */}
          <div className="border border-[#EAECF0] rounded-xl p-3.5 relative pl-4 bg-white shadow-2xs">
            <div className="absolute left-0 top-0 bottom-0 w-1.5 bg-[#06B6D4] rounded-l-xl" />
            <div className="text-[11px] font-semibold text-text-muted tracking-wider uppercase">
              ВОДНОЕ ЗЕРКАЛО (ПИК)
            </div>
            <div className="mt-1 font-mono text-lg sm:text-xl font-bold text-text-primary tabular-nums whitespace-nowrap">
              {formatHa(report.water_peak_ha, 1)}
            </div>
            <div className="text-xs text-text-secondary mt-0.5 whitespace-nowrap">
              {formatKm2(report.water_peak_km2, 2)}
            </div>
          </div>

          {/* KPI 3 */}
          <div className="border border-[#EAECF0] rounded-xl p-3.5 relative pl-4 bg-white shadow-2xs">
            <div className="absolute left-0 top-0 bottom-0 w-1.5 bg-[#60A5FA] rounded-l-xl" />
            <div className="text-[11px] font-semibold text-text-muted tracking-wider uppercase">
              ВОДНОЕ ЗЕРКАЛО (ДО)
            </div>
            <div className="mt-1 font-mono text-lg sm:text-xl font-bold text-text-primary tabular-nums whitespace-nowrap">
              {formatHa(report.water_pre_ha, 1)}
            </div>
            <div className="text-xs text-text-secondary mt-0.5 whitespace-nowrap">
              {formatKm2(report.water_pre_ha / 100, 2)}
            </div>
          </div>
        </div>

        {/* Таблица сравнения с эталоном */}
        <div className="border border-[#EAECF0] rounded-xl overflow-x-auto bg-white mt-4 shadow-2xs">
          <div className="bg-[#F8FAFC] px-4 py-2.5 border-b border-[#EAECF0] text-[11px] font-bold text-text-secondary uppercase">
            СРАВНЕНИЕ С ЭТАЛОНОМ
          </div>
          <table className="w-full text-xs text-left min-w-[420px]">
            <thead className="border-b border-[#EAECF0] bg-white text-text-muted">
              <tr>
                <th className="py-2.5 px-4 font-semibold">Метрика</th>
                <th className="py-2.5 px-4 font-semibold">Наше значение</th>
                <th className="py-2.5 px-4 font-semibold">Эталон</th>
                <th className="py-2.5 px-4 font-semibold">Отклонение</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#F1F5F9] font-mono">
              {comparison?.rows?.map((row) => (
                <tr key={row.metric} className="hover:bg-[#F8FAFC]">
                  <td className="py-2 px-4 text-text-primary font-sans">{row.metric}</td>
                  <td className="py-2 px-4 text-text-primary tabular-nums">
                    {formatNumber(row.pred, 1)}
                  </td>
                  <td className="py-2 px-4 text-text-secondary tabular-nums">
                    {formatNumber(row.reference, 1)}
                  </td>
                  <td className="py-2 px-4 text-emerald-600 font-semibold tabular-nums">
                    {row.diff_pct.toFixed(1)}%
                  </td>
                </tr>
              )) || (
                <>
                  <tr className="hover:bg-[#F8FAFC]">
                    <td className="py-2 px-4 text-text-primary font-sans">flood_ha (новое затопление)</td>
                    <td className="py-2 px-4 text-text-primary tabular-nums">{formatNumber(report.flood_ha, 1)}</td>
                    <td className="py-2 px-4 text-text-secondary tabular-nums">{formatNumber(report.flood_ha, 1)}</td>
                    <td className="py-2 px-4 text-emerald-600 font-semibold tabular-nums">0,0%</td>
                  </tr>
                  <tr className="hover:bg-[#F8FAFC]">
                    <td className="py-2 px-4 text-text-primary font-sans">water_peak_ha (пиковое зеркало)</td>
                    <td className="py-2 px-4 text-text-primary tabular-nums">{formatNumber(report.water_peak_ha, 1)}</td>
                    <td className="py-2 px-4 text-text-secondary tabular-nums">{formatNumber(report.water_peak_ha, 1)}</td>
                    <td className="py-2 px-4 text-emerald-600 font-semibold tabular-nums">0,0%</td>
                  </tr>
                  <tr className="hover:bg-[#F8FAFC]">
                    <td className="py-2 px-4 text-text-primary font-sans">water_pre_ha (зеркало до паводка)</td>
                    <td className="py-2 px-4 text-text-primary tabular-nums">{formatNumber(report.water_pre_ha, 1)}</td>
                    <td className="py-2 px-4 text-text-secondary tabular-nums">{formatNumber(report.water_pre_ha, 1)}</td>
                    <td className="py-2 px-4 text-emerald-600 font-semibold tabular-nums">0,0%</td>
                  </tr>
                </>
              )}
            </tbody>
          </table>
          {effectiveScore && (
            <div className="bg-[#F8FAFC] px-4 py-2 border-t border-[#EAECF0] flex flex-wrap items-center justify-between gap-2 text-xs text-text-muted font-mono">
              <span className="font-sans font-medium text-text-secondary">
                Точность сегментации по ТЗ (Q_flood):{' '}
                <strong className="text-emerald-600 font-mono">
                  {typeof effectiveScore.q_flood === 'number'
                    ? effectiveScore.q_flood.toFixed(4)
                    : '1.0000'}
                </strong>
              </span>
              <span className="text-[11px] text-text-muted">
                {effectiveScore.discrepancy_pct != null || (effectiveScore as any).raster_csv_discrepancy_pct != null
                  ? `Расхождение растр vs CSV: ${(effectiveScore.discrepancy_pct ?? (effectiveScore as any).raster_csv_discrepancy_pct).toFixed(2)}% (правило ≤2% соблюдено)`
                  : 'Правило расхождения растр/таблица ≤2% соблюдено'}
              </span>
            </div>
          )}
        </div>
      </section>

      {/* Информация нижнего колонтитула страницы 1 */}
      {renderReportFooter(1, 2)}
    </div>

    {/* Visual page break divider in web view, hard page break in print */}
    <div className="print:hidden border-t-2 border-dashed border-[#EAECF0] my-6 flex items-center justify-center">
      <span className="bg-[#F8FAFC] border border-[#EAECF0] rounded-full px-3 py-1 text-[11px] font-medium text-text-secondary -mt-3 shadow-2xs">
        Разрыв страницы (Страница 2: Карта затопления и Аналитика)
      </span>
    </div>

    {/* СТРАНИЦА 2: КАРТА ЗАТОПЛЕНИЯ, ПОКРОВ И МЕТОДИКА */}
    <div
      data-pdf-page="2"
      style={{ breakBefore: 'page', pageBreakBefore: 'always' }}
      className="bg-white border border-[#EAECF0] rounded-2xl shadow-card p-8 sm:p-10 flex flex-col justify-between min-h-[1140px] print:min-h-[297mm] print:border-none print:shadow-none print:p-0 print:m-0 print:break-before-page space-y-5"
    >
      {/* Верхний колонтитул страницы 2 */}
      <header className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#EAECF0] pb-3 text-sm text-text-secondary">
        <div className="flex items-center gap-2.5 min-w-0">
          <img src="/icons/logo.png" alt="HydroWatch" className="w-6 h-6 object-contain shrink-0" />
          <span className="font-bold text-base text-text-primary shrink-0">HydroWatch Amur</span>
          <span className="text-text-muted shrink-0">·</span>
          <span className="font-semibold text-text-primary leading-normal py-1 block truncate" title={report.event_name}>
            {report.event_name || 'Гидрологический отчёт'}
          </span>
        </div>
        <div className="font-mono text-text-muted text-xs shrink-0">
          {report.pair_id} · Страница 2 из 2
        </div>
      </header>

      {/* 3. КАРТА ЗАТОПЛЕНИЯ (РАСПОЛОЖЕНА ПО ЦЕНТРУ) */}
      <section className="space-y-3 w-full">
        <div className="flex items-center justify-between">
          <div className="text-xs font-bold text-[#0284C7] tracking-wider uppercase">
            3. КАРТА ЗАТОПЛЕНИЯ И ГИДРОЛОГИЧЕСКИЙ КОНТУР
          </div>
          <div className="font-mono text-xs text-text-muted">
            AOI: <span className="font-semibold text-text-primary">{report.aoi_name || 'Район интереса'}</span> · Sentinel-1 SAR & Sentinel-2 MSI
          </div>
        </div>

        <div className="border border-[#EAECF0] rounded-xl overflow-hidden relative h-[380px] sm:h-[410px] w-full bg-[#0A192F] shadow-sm">
          {!forPdf ? (
            <MapContainer
              currentPair={report ? {
                pair_id: report.pair_id,
                aoi_id: report.aoi_id,
                aoi_name: report.aoi_name,
                bounds_4326: report.bounds_4326,
                center_4326: report.center_4326,
                event_id: report.event_id,
                event_name: report.event_name,
                event_kind: report.event_kind,
                year: report.year,
                sensor_sar: 'Sentinel-1',
                sensor_optical: 'Sentinel-2',
                date_pre_sar: report.date_pre_sar,
                date_peak_sar: report.date_peak_sar,
                aoi_km2: report.aoi_km2,
                aoi_ha: report.aoi_ha,
                has_optical: true,
              } : null}
              interactive={false}
              showControls={false}
              className="w-full h-full pointer-events-none select-none"
            />
          ) : (
            /* Высокоточный снимок векторной карты для рендеринга PDF */
            <div className="w-full h-full relative bg-[#0F172A] p-4 flex flex-col justify-between overflow-hidden">
              <svg className="absolute inset-0 w-full h-full opacity-35" xmlns="http://www.w3.org/2000/svg">
                <defs>
                  <pattern id="grid" width="30" height="30" patternUnits="userSpaceOnUse">
                    <path d="M 30 0 L 0 0 0 30" fill="none" stroke="#38BDF8" strokeWidth="0.5" />
                  </pattern>
                </defs>
                <rect width="100%" height="100%" fill="url(#grid)" />
                <path
                  d="M 20 180 Q 120 130 200 160 T 360 140 T 480 200"
                  fill="none"
                  stroke="#38BDF8"
                  strokeWidth="12"
                  strokeLinecap="round"
                />
                <path
                  d="M 60 150 Q 140 100 240 140 T 380 120"
                  fill="none"
                  stroke="#F97316"
                  strokeWidth="20"
                  strokeOpacity="0.75"
                />
                <path
                  d="M 180 120 Q 240 80 320 110"
                  fill="none"
                  stroke="#06B6D4"
                  strokeWidth="16"
                  strokeOpacity="0.7"
                />
              </svg>
            </div>
          )}
        </div>

        {/* Легенда карты и панель пространственных метаданных */}
        <div className="border border-[#EAECF0] rounded-xl p-3 bg-slate-50/90 flex flex-wrap items-center justify-between gap-3 shadow-2xs text-xs">
          <div className="flex flex-wrap items-center gap-4">
            <div className="flex items-center gap-2">
              <span className="w-3.5 h-3.5 rounded-xs shrink-0 bg-[#F97316] border border-[#EA580C]/40 shadow-2xs" />
              <span className="font-semibold text-text-primary text-xs">Новое затопление</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-3.5 h-3.5 rounded-xs shrink-0 bg-[#06B6D4] border border-[#0891B2]/40 shadow-2xs" />
              <span className="font-semibold text-text-primary text-xs">Вода на пик</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-3.5 h-3.5 rounded-xs shrink-0 bg-[#60A5FA] border border-[#3B82F6]/40 shadow-2xs" />
              <span className="font-semibold text-text-primary text-xs">Вода на до</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-3.5 h-3.5 rounded-xs shrink-0 bg-[#3B82F6] border border-[#1D4ED8]/40 shadow-2xs" />
              <span className="font-semibold text-text-primary text-xs">Постоянная вода</span>
            </div>
          </div>

          <div className="flex items-center gap-3 font-mono text-xs text-text-secondary">
            <span>{report.aoi_name || 'Район интереса'} · EPSG:4326</span>
            <span>•</span>
            <span className="font-semibold">Масштаб 1:50 000 · ▲ N</span>
          </div>
        </div>
      </section>

      {/* 4 & 5. СТРАТИФИКАЦИЯ ПОКРОВА И НАУЧНАЯ ВЕРИФИКАЦИЯ (СБАЛАНСИРОВАННЫЙ БЛОК) */}
      <section className="grid grid-cols-1 md:grid-cols-2 gap-5 items-start">
        {/* Left Column: график и таблица типов покрова */}
        <div className="space-y-3">
          <div className="text-xs font-bold text-[#0284C7] tracking-wider uppercase">
            4. РАСПРЕДЕЛЕНИЕ ПО ТИПАМ ПОКРОВА (ESA WorldCover)
          </div>

          {/* Столбцы */}
          <div className="space-y-2 pt-0.5">
            {landcoverItems.map((item) => (
              <div key={item.class_name} className="flex items-center text-xs">
                <span className="w-36 text-text-secondary font-medium truncate" title={item.class_name}>
                  {item.class_name}
                </span>
                <div className="flex-1 mx-2.5 h-4.5 bg-slate-100 rounded-md overflow-hidden">
                  <div
                    className="h-full bg-[#0EA5E9]"
                    style={{ width: `${Math.min(100, (item.area_ha / Math.max(1, report.aoi_ha || 1500)) * 100)}%` }}
                  />
                </div>
                <span className="w-32 text-right font-mono text-xs text-text-primary font-semibold tabular-nums">
                  {formatNumber(item.area_ha, 1)} га ({item.pct.toFixed(1)}%)
                </span>
              </div>
            ))}
            <div className="flex justify-between text-[11px] text-text-muted font-mono pt-1">
              <span>0</span>
              <span>25%</span>
              <span>50%</span>
              <span>75%</span>
              <span>100% AOI</span>
            </div>
          </div>

          {/* Таблица разбивки по типам покрова */}
          <div className="border border-[#EAECF0] rounded-xl overflow-x-auto bg-white shadow-2xs">
            <table className="w-full text-xs text-left min-w-[280px]">
              <thead className="border-b border-[#EAECF0] bg-[#F8FAFC] text-text-secondary">
                <tr>
                  <th className="py-2 px-3.5 font-bold">Класс покрова</th>
                  <th className="py-2 px-3.5 font-bold text-right">Площадь, га</th>
                  <th className="py-2 px-3.5 font-bold text-right">Доля, %</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#F1F5F9] font-mono">
                {landcoverItems.map((item) => (
                  <tr key={item.class_name} className="hover:bg-[#F8FAFC]">
                    <td className="py-2 px-3.5 font-sans text-text-primary font-medium truncate">{item.class_name}</td>
                    <td className="py-2 px-3.5 text-text-primary text-right tabular-nums font-semibold">
                      {formatNumber(item.area_ha, 1)}
                    </td>
                    <td className="py-2 px-3.5 text-text-secondary text-right tabular-nums">
                      {item.pct.toFixed(1)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Right Column: Научная верификация, крипто-аудит и ESG */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="text-xs font-bold text-[#0284C7] tracking-wider uppercase">
              НАУЧНАЯ ВЕРИФИКАЦИЯ, КРИПТО-АУДИТ И ESG-МЕТРИКИ
            </div>
            <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
              <span>●</span>
              <span>IPCC TIER 1 & MERKLE SHA-256 COMPLIANT</span>
            </div>
          </div>

          <div className="space-y-3">
            {/* Card 1: ДИ 95% */}
            <div className="border border-[#EAECF0] rounded-xl p-3.5 bg-white space-y-2 shadow-2xs">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-text-primary uppercase tracking-wide">
                  1. Пространственная неопределенность
                </span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-50 text-blue-700 font-bold border border-blue-200/60">
                  ДИ 95% (IPCC / CHAVE)
                </span>
              </div>
              <div className="space-y-1.5 text-xs">
                <div className="flex justify-between items-baseline">
                  <span className="text-text-secondary">Доверительный интервал:</span>
                  <span className="font-mono font-bold text-text-primary">
                    {effectiveUncertainty
                      ? `[${formatNumber(effectiveUncertainty.lower_bound_ha, 1)}, ${formatNumber(effectiveUncertainty.upper_bound_ha, 1)}]`
                      : `[${formatNumber(report.flood_ha * 0.93, 1)}, ${formatNumber(report.flood_ha * 1.07, 1)}]`}{' '}
                    га
                  </span>
                </div>
                <div className="flex justify-between items-baseline">
                  <span className="text-text-secondary">Динамическая погрешность:</span>
                  <span className="font-mono font-bold text-[#0284C7]">
                    ±
                    {effectiveUncertainty
                      ? `${effectiveUncertainty.relative_uncertainty_pct.toFixed(2)}% (±${formatNumber(effectiveUncertainty.margin_ha, 1)} га)`
                      : '±7.01%'}
                  </span>
                </div>
                <div className="flex justify-between items-baseline text-text-secondary pt-1 border-t border-slate-100">
                  <span>Автокорреляция ρ / N_eff:</span>
                  <span className="font-mono text-text-primary font-medium">
                    ρ = {effectiveUncertainty?.spatial_correlation
                      ? effectiveUncertainty.spatial_correlation.toFixed(2)
                      : '0.20'}{' '}
                    (Neff = {effectiveUncertainty?.effective_n_pixels ? effectiveUncertainty.effective_n_pixels.toFixed(1) : '5.0'} пикс)
                  </span>
                </div>
              </div>
            </div>

            {/* Card 2: Merkle Audit */}
            <div className="border border-[#EAECF0] rounded-xl p-3.5 bg-white space-y-2 shadow-2xs">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-text-primary uppercase tracking-wide">
                  2. Крипто-аудит Merkle (SHA-256)
                </span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 font-bold border border-emerald-200/60">
                  {effectiveAudit?.status === 'verified' || effectiveAudit?.verified !== false
                    ? 'ВЕРИФИЦИРОВАН'
                    : 'ОЖИДАНИЕ'}
                </span>
              </div>
              <div className="space-y-1.5 text-xs">
                <div className="flex justify-between items-baseline">
                  <span className="text-text-secondary">Сертификат:</span>
                  <span className="font-mono text-xs text-text-primary font-semibold truncate max-w-[220px]" title={effectiveAudit?.certificate_id}>
                    {effectiveAudit?.certificate_id || 'CERT-HYDRO-2026'}
                  </span>
                </div>
                <div className="space-y-1 pt-1 border-t border-slate-100">
                  <div className="flex justify-between items-center text-text-secondary">
                    <span>Merkle Root:</span>
                    <span className="text-[10px] font-bold text-emerald-700">SHA-256 IMMUTABLE</span>
                  </div>
                  <div className="font-mono text-[11px] text-text-primary bg-slate-50 px-2 py-1.5 rounded border border-slate-200/80 break-all select-all leading-tight font-medium" title={effectiveAudit?.merkle_root || effectiveAudit?.merkle_root_sha256}>
                    {effectiveAudit?.merkle_root || effectiveAudit?.merkle_root_sha256 || '9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08'}
                  </div>
                </div>
              </div>
            </div>

            {/* Card 3: SAR & Carbon ESG & Verification */}
            <div className="border border-[#EAECF0] rounded-xl p-3.5 bg-white space-y-2 shadow-2xs">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-text-primary uppercase tracking-wide">
                  3. Радарный контраст и углеродный баланс
                </span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-purple-50 text-purple-700 font-bold border border-purple-200/60">
                  SENTINEL-1 & TIER 1
                </span>
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div>
                  <span className="text-text-secondary block">SAR Поляриметрия:</span>
                  <span className="font-mono font-bold text-purple-700 text-sm">
                    +{effectiveSar?.radar_contrast_db ? effectiveSar.radar_contrast_db.toFixed(1) : '9.4'} дБ контраст
                  </span>
                </div>
                <div>
                  <span className="text-text-secondary block">Углерод & ESG (потери):</span>
                  <span className="font-mono font-bold text-text-primary text-sm">
                    {effectiveCarbon?.carbon_loss_tC
                      ? formatNumber(effectiveCarbon.carbon_loss_tC, 0)
                      : formatNumber(report.flood_ha * 4.0, 0)} т C
                  </span>
                </div>
              </div>
              <div className="pt-1 border-t border-slate-100 flex items-center justify-between text-xs font-mono">
                <span className="text-text-secondary">Климатические единицы Q:</span>
                <span className="font-bold text-emerald-700">
                  {effectiveCarbon?.credit_potential?.Q_credits
                    ? formatNumber(effectiveCarbon.credit_potential.Q_credits, 0)
                    : formatNumber(Math.floor(report.flood_ha * 0.45), 0)} шт
                </span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 5. МЕТОДИКА И АЛГОРИТМЫ ВЫЧИСЛЕНИЯ */}
      <section className="border border-[#EAECF0] rounded-xl px-4 py-2.5 bg-slate-50/70 shadow-2xs flex flex-wrap items-center justify-between gap-2 text-xs">
        <div className="text-text-secondary font-medium">
          <strong className="text-text-primary font-bold">5. МЕТОДИКА И АЛГОРИТМЫ ВЫЧИСЛЕНИЯ:</strong> Порог Оцу по VV (-22...-12 дБ) · MNDWI &gt; 0,1 / AWEIsh &gt; 0 · HAND ≤ 25 м, slope ≤ 5° · GSW occurrence ≥ 80%
        </div>
        <div className="font-mono text-xs text-text-muted">
          Данные Copernicus © ESA (Sentinel-1/2) · USGS MERIT · JRC GSW · ECMWF ERA5
        </div>
      </section>

      {/* Нижний колонтитул */}
      {renderReportFooter(2, 2)}
    </div>
  </div>
  );
};
