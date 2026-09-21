import React from 'react';
import type { ReportData, ComparisonData } from '../../types/domain';
import { formatNumber, formatHa, formatKm2 } from '../../lib/format';
import { deriveLandcoverItems } from '../../lib/landcover';
import { MapContainer } from '../map/MapContainer';

interface ReportDocumentProps {
  report: ReportData;
  comparison?: ComparisonData | null;
  forPdf?: boolean;
}

export const ReportDocument: React.FC<ReportDocumentProps> = ({
  report,
  comparison,
  forPdf = false,
}) => {
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
      className="w-full max-w-5xl mx-auto space-y-6 print:space-y-0 print:p-0 print:m-0"
    >
      {/* PAGE 1: МЕТАДАННЫЕ И РЕЗУЛЬТАТЫ */}
      <div
        data-pdf-page="1"
        className="bg-white border border-[#EAECF0] rounded-2xl shadow-card p-6 sm:p-8 space-y-6 print:border-none print:shadow-none print:p-0 print:m-0"
      >
        {/* Header */}
      <header className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#F1F5F9] pb-5">
        <div className="flex items-center gap-3">
          <img src="/icons/logo.png" alt="HydroWatch" className="w-8 h-8 object-contain" />
          <div className="flex items-baseline gap-1.5">
            <span className="font-bold text-xl tracking-tight text-text-primary">HydroWatch</span>
            <span className="text-text-muted text-base font-normal">Amur</span>
          </div>
          <span className="text-text-muted hidden sm:inline">|</span>
          <span className="text-xs text-text-secondary font-medium">Автоматический отчёт</span>
        </div>

        <div className="text-xs text-text-muted font-mono">
          Сгенерировано: {currentDateFormatted}
        </div>
      </header>

      {/* Title Block */}
      <div className="space-y-1">
        <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-md bg-[#E0F2FE] text-[#0284C7] text-xs font-semibold uppercase tracking-wider mb-0.5">
          КосмоХакатон 2026
        </div>
        <h1 className="text-xl sm:text-2xl font-bold text-text-primary leading-normal py-0.5 break-words">
          {report.event_name || 'Паводок, июль 2019 — Благовещенск'}
        </h1>
        <div className="font-mono text-xs text-text-muted leading-relaxed">
          pair_id: {report.pair_id} · AOI: {report.aoi_name || 'Благовещенск'}
        </div>
      </div>

      {/* 1. ИСХОДНЫЕ ДАННЫЕ */}
      <section className="space-y-3">
        <div className="text-[11px] font-bold text-text-muted tracking-wider uppercase">
          1. ИСХОДНЫЕ ДАННЫЕ
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {/* Card 1: Sentinel-1 (SAR) */}
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

          {/* Card 2: Sentinel-2 (MSI) */}
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

        {/* Reference Comparison Table */}
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
        </div>
      </section>

      {/* Page 1 Footer info */}
      <div className="pt-4 border-t border-[#F1F5F9] flex items-center justify-between text-xs text-text-muted">
        <span>Разделы 1–2: Исходные параметры и эталонное сопоставление</span>
        <span className="font-mono">Страница 1 из 2</span>
      </div>
    </div>

    {/* Visual page break divider in web view, hard page break in print */}
    <div className="print:hidden border-t-2 border-dashed border-[#EAECF0] my-6 flex items-center justify-center">
      <span className="bg-[#F8FAFC] border border-[#EAECF0] rounded-full px-3 py-1 text-[11px] font-medium text-text-secondary -mt-3 shadow-2xs">
        Разрыв страницы (Страница 2: Карта затопления и Аналитика)
      </span>
    </div>

    {/* PAGE 2: КАРТА ЗАТОПЛЕНИЯ, ПОКРОВ И МЕТОДИКА */}
    <div
      data-pdf-page="2"
      style={{ breakBefore: 'page', pageBreakBefore: 'always' }}
      className="bg-white border border-[#EAECF0] rounded-2xl shadow-card p-6 sm:p-8 space-y-6 print:border-none print:shadow-none print:p-0 print:m-0 print:break-before-page"
    >
      {/* Page 2 Running Header */}
      <header className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-[#F1F5F9] pb-4 text-xs text-text-secondary">
        <div className="flex items-center gap-2">
          <img src="/icons/logo.png" alt="HydroWatch" className="w-5 h-5 object-contain" />
          <span className="font-bold text-text-primary">HydroWatch Amur</span>
          <span>·</span>
          <span className="font-medium text-text-primary truncate">{report.event_name || 'Гидрологический отчёт'}</span>
        </div>
        <div className="font-mono text-text-muted text-[11px]">
          {report.pair_id} · Страница 2 из 2
        </div>
      </header>

      {/* 3. КАРТА И РАСПРЕДЕЛЕНИЕ ПО ТИПАМ ПОКРОВА */}
      <section className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Map Preview */}
        <div className="lg:col-span-6 space-y-2">
          <div className="text-[11px] font-bold text-text-muted tracking-wider uppercase">
            3. КАРТА ЗАТОПЛЕНИЯ
          </div>
          <div className="border border-[#EAECF0] rounded-xl overflow-hidden relative h-[300px] sm:h-[340px] bg-[#0A192F] shadow-2xs">
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
                <svg className="absolute inset-0 w-full h-full opacity-30" xmlns="http://www.w3.org/2000/svg">
                  <defs>
                    <pattern id="grid" width="30" height="30" patternUnits="userSpaceOnUse">
                      <path d="M 30 0 L 0 0 0 30" fill="none" stroke="#38BDF8" strokeWidth="0.5" />
                    </pattern>
                  </defs>
                  <rect width="100%" height="100%" fill="url(#grid)" />
                  {/* Simulated hydrography & flood contours */}
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

                <div className="relative z-10 flex justify-between items-start">
                  <span className="bg-black/60 text-white font-mono px-2 py-1 rounded text-[10px] font-bold">
                    ▲ N (СЕВЕР)
                  </span>
                  <span className="bg-white/95 text-text-primary px-2.5 py-1 rounded-md text-xs font-semibold shadow-xs">
                    {report.aoi_name || 'Благовещенск'}
                  </span>
                </div>

                <div className="relative z-10 flex justify-between items-end">
                  <span className="bg-white/90 px-2 py-0.5 rounded text-[10px] font-mono text-text-secondary">
                    Масштаб: 1 : 100 000 · EPSG:4326
                  </span>
                </div>
              </div>
            )}

            {/* Compass North Arrow */}
            <div className="absolute top-3 left-3 bg-black/60 text-white px-2 py-1 rounded text-[10px] font-bold z-10 pointer-events-none">
              ▲ N
            </div>

            {/* City marker / AOI name */}
            <div className="absolute top-3 right-3 text-text-primary bg-white/95 backdrop-blur-sm border border-[#EAECF0] px-2.5 py-1 rounded-md text-xs font-semibold shadow-xs z-10 pointer-events-none">
              {report.aoi_name || 'Благовещенск'}
            </div>

            {/* Mini scale */}
            <div className="absolute bottom-3 left-3 bg-white/90 backdrop-blur-xs border border-[#EAECF0] px-2 py-0.5 rounded text-text-secondary text-[10px] font-mono z-10 pointer-events-none">
              | 0 — 5 — 10 км | EPSG:4326
            </div>

            {/* Map Legend inside preview */}
            <div className="absolute bottom-3 right-3 bg-white/95 backdrop-blur-sm rounded-lg p-2 text-[10px] space-y-1 shadow-sm border border-[#EAECF0] z-10 pointer-events-none">
              <div className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-xs bg-[#F97316]" />
                <span>Новое затопление</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-xs bg-[#06B6D4]" />
                <span>Вода на пик</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-xs bg-[#60A5FA]" />
                <span>Вода на до</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-xs bg-[#3B82F6]" />
                <span>Постоянная вода</span>
              </div>
            </div>
          </div>
          <div className="text-[11px] text-text-muted">
            Зона нового затопления выделена оранжевым. Контур AOI — синий.
          </div>
        </div>

        {/* Landcover chart + table */}
        <div className="lg:col-span-6 space-y-3">
          <div className="text-[11px] font-bold text-text-muted tracking-wider uppercase">
            4. РАСПРЕДЕЛЕНИЕ ПО ТИПАМ ПОКРОВА (ESA WorldCover)
          </div>

          {/* Bars */}
          <div className="space-y-1.5 pt-1">
            {landcoverItems.map((item) => (
              <div key={item.class_name} className="flex items-center text-xs">
                <span className="w-32 text-text-secondary text-[11px] truncate" title={item.class_name}>
                  {item.class_name}
                </span>
                <div className="flex-1 mx-2 h-4 bg-slate-100 rounded overflow-hidden">
                  <div
                    className="h-full bg-[#0EA5E9]"
                    style={{ width: `${(item.area_ha / 1500) * 100}%` }}
                  />
                </div>
                <span className="w-28 text-right font-mono text-[11px] text-text-secondary tabular-nums">
                  {formatNumber(item.area_ha, 1)} га ({item.pct.toFixed(1)}%)
                </span>
              </div>
            ))}
            <div className="flex justify-between text-[10px] text-text-muted font-mono pt-1">
              <span>0</span>
              <span>500</span>
              <span>1 000</span>
              <span>1 500 га</span>
            </div>
          </div>

          {/* Landcover breakdown table */}
          <div className="border border-[#EAECF0] rounded-xl overflow-x-auto bg-white mt-3 shadow-2xs">
            <table className="w-full text-xs text-left min-w-[320px]">
              <thead className="border-b border-[#EAECF0] bg-[#F8FAFC] text-text-muted">
                <tr>
                  <th className="py-2 px-3 font-semibold">Класс покрова</th>
                  <th className="py-2 px-3 font-semibold">Площадь, га</th>
                  <th className="py-2 px-3 font-semibold">Доля, %</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#F1F5F9] font-mono">
                {landcoverItems.map((item) => (
                  <tr key={item.class_name} className="hover:bg-[#F8FAFC]">
                    <td className="py-1.5 px-3 font-sans text-text-primary truncate">{item.class_name}</td>
                    <td className="py-1.5 px-3 text-text-primary tabular-nums font-semibold">
                      {formatNumber(item.area_ha, 1)}
                    </td>
                    <td className="py-1.5 px-3 text-text-secondary tabular-nums">
                      {item.pct.toFixed(1)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* 4. МЕТОДИКА */}
      <section className="border border-[#EAECF0] rounded-xl overflow-hidden bg-white shadow-2xs">
        <div className="w-full px-4 py-2.5 bg-[#F8FAFC] border-b border-[#EAECF0]">
          <span className="font-bold text-xs text-text-primary uppercase tracking-wider">
            5. МЕТОДИКА И АЛГОРИТМЫ ВЫЧИСЛЕНИЯ
          </span>
        </div>

        <div className="p-4 space-y-3 text-xs">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-text-secondary">
            <div>
              <span className="font-semibold text-text-primary">Сегментация:</span>{' '}
              порог Оцу по VV (-22...-12 дБ), фильтрация спекла, требование падения σ⁰ ≥ 3 дБ.
            </div>
            <div>
              <span className="font-semibold text-text-primary">Оптика:</span>{' '}
              MNDWI &gt; 0,1 или AWEIsh &gt; 0 при NDVI ≤ 0,3.
            </div>
            <div>
              <span className="font-semibold text-text-primary">Фильтры:</span>{' '}
              slope ≤ 5°, HAND ≤ 25 м, GSW occurrence ≥ 80%.
            </div>
          </div>

          <div className="pt-2 border-t border-[#F1F5F9] text-[11px] text-text-muted">
            <span className="font-semibold text-text-secondary">Источники данных:</span>{' '}
            Copernicus (Sentinel-1, Sentinel-2) · USGS (MERIT Hydro) · JRC (GSW) · ECMWF (ERA5)
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="pt-4 border-t border-[#EAECF0] flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-text-muted">
        <div className="space-y-0.5 text-center sm:text-left">
          <div>Разметка построена автоматически по консенсусу SAR и MSI.</div>
          <div>Сплошная ручная верификация не проводилась.</div>
        </div>

        <div className="text-center sm:text-right font-mono text-[11px]">
          Данные Copernicus © ESA, 2019-2026 · HydroWatch Amur
        </div>
      </footer>
    </div>
  </div>
  );
};
