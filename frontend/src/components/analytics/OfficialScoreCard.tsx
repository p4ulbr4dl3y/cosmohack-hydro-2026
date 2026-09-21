import React, { useEffect, useState } from 'react';
import { Award, CheckCircle2, AlertCircle, ChevronDown, ChevronUp, ExternalLink } from 'lucide-react';
import { Link } from 'react-router-dom';
import { apiClient } from '../../api/client';
import type { OfficialMetrics, SubmissionValidation } from '../../types/domain';

interface OfficialScoreCardProps {
  activePairId?: string;
  isLoading?: boolean;
}

export const OfficialScoreCard: React.FC<OfficialScoreCardProps> = ({ activePairId, isLoading = false }) => {
  const [metrics, setMetrics] = useState<OfficialMetrics | null>(null);
  const [validation, setValidation] = useState<SubmissionValidation | null>(null);
  const [loadingData, setLoadingData] = useState(false);
  const [showTable, setShowTable] = useState(false);

  useEffect(() => {
    let isMounted = true;
    setLoadingData(true);
    Promise.all([
      apiClient.fetchOfficialMetrics().catch(() => null),
      apiClient.validateSubmission().catch(() => null),
    ])
      .then(([metricsRes, valRes]) => {
        if (isMounted) {
          setMetrics(metricsRes);
          setValidation(valRes);
        }
      })
      .finally(() => {
        if (isMounted) setLoadingData(false);
      });

    return () => {
      isMounted = false;
    };
  }, []);

  const activeDetail = metrics?.details.find((d) => d.pair_id === activePairId) || null;

  if (isLoading || loadingData) {
    return (
      <div className="bg-white border border-[#EAECF0] rounded-xl p-4 shadow-2xs animate-pulse">
        <div className="h-4 bg-slate-200 rounded w-2/3 mb-2" />
        <div className="h-8 bg-slate-100 rounded w-1/2 mb-3" />
        <div className="grid grid-cols-4 gap-2">
          <div className="h-10 bg-slate-100 rounded" />
          <div className="h-10 bg-slate-100 rounded" />
          <div className="h-10 bg-slate-100 rounded" />
          <div className="h-10 bg-slate-100 rounded" />
        </div>
      </div>
    );
  }

  if (!metrics) return null;

  return (
    <div className="bg-gradient-to-br from-[#F0F9FF] to-white border border-[#BAE6FD] rounded-xl p-4 shadow-2xs text-xs space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5 font-semibold text-slate-900">
          <Award className="w-4 h-4 text-[#0284C7]" />
          <span>Официальная метрика ТЗ</span>
        </div>
        <div className="flex items-center gap-1">
          {validation?.is_valid ? (
            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-800 text-[10px] font-bold">
              <CheckCircle2 className="w-3 h-3" />
              <span>Сабмит валиден</span>
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-amber-100 text-amber-800 text-[10px] font-bold">
              <AlertCircle className="w-3 h-3" />
              <span>Проверка</span>
            </span>
          )}
        </div>
      </div>

      {/* Main Score Banner */}
      <div className="bg-white/80 border border-[#E0F2FE] rounded-lg p-2.5 flex items-center justify-between">
        <div>
          <div className="text-[10px] text-text-secondary uppercase tracking-wider font-semibold">
            Итоговый Score
          </div>
          <div className="text-xl font-black text-[#0284C7] tracking-tight">
            {metrics.score.toFixed(4)}
          </div>
        </div>
        <div className="text-right">
          <div className="text-[10px] text-text-secondary">Баллы критерия</div>
          <div className="text-sm font-bold text-slate-800">
            {metrics.technical_points} / 7.00
          </div>
        </div>
      </div>

      {/* 4 Components Formula Breakdown */}
      <div className="grid grid-cols-4 gap-1.5 text-center">
        <div className="bg-white/90 border border-slate-200 rounded p-1.5">
          <div className="text-[9px] text-text-secondary">Q_flood (0.45)</div>
          <div className="text-xs font-bold text-slate-800">{metrics.q_flood.toFixed(3)}</div>
        </div>
        <div className="bg-white/90 border border-slate-200 rounded p-1.5">
          <div className="text-[9px] text-text-secondary">Q_peak (0.25)</div>
          <div className="text-xs font-bold text-slate-800">{metrics.q_water_peak.toFixed(3)}</div>
        </div>
        <div className="bg-white/90 border border-slate-200 rounded p-1.5">
          <div className="text-[9px] text-text-secondary">Q_pre (0.15)</div>
          <div className="text-xs font-bold text-slate-800">{metrics.q_water_pre.toFixed(3)}</div>
        </div>
        <div className="bg-white/90 border border-slate-200 rounded p-1.5">
          <div className="text-[9px] text-text-secondary">Spec_base (0.15)</div>
          <div className="text-xs font-bold text-slate-800">{metrics.spec_base.toFixed(3)}</div>
        </div>
      </div>

      {/* Active Pair Accuracy Detail */}
      {activeDetail && (
        <div className="bg-slate-50 border border-slate-200/80 rounded-lg p-2 space-y-1">
          <div className="flex items-center justify-between text-[11px] font-semibold text-slate-800">
            <span>Точность по текущей паре:</span>
            <span className="font-mono text-[#0284C7]">q_flood = {activeDetail.q_flood.toFixed(4)}</span>
          </div>
          <div className="flex items-center justify-between text-[10px] text-text-secondary">
            <span>Расчет vs Эталон:</span>
            <span>{activeDetail.flood_sub_ha} га vs {activeDetail.flood_ref_ha} га (Δ {activeDetail.flood_abs_diff_ha} га)</span>
          </div>
          {typeof activeDetail.raster_csv_discrepancy_pct === 'number' && (
            <div className="flex items-center justify-between text-[10px] text-text-secondary">
              <span>Расхождение растр-CSV:</span>
              <span className={activeDetail.raster_csv_discrepancy_pct <= 2.0 ? 'text-emerald-700 font-medium' : 'text-rose-600 font-medium'}>
                {activeDetail.raster_csv_discrepancy_pct.toFixed(2)}% (правило ≤ 2%)
              </span>
            </div>
          )}
        </div>
      )}

      {/* Expandable Breakdown Button */}
      <div className="flex items-center justify-between pt-1">
        <button
          onClick={() => setShowTable(!showTable)}
          className="flex items-center gap-1 text-[11px] font-medium text-[#0284C7] hover:text-[#0369A1] transition-colors cursor-pointer"
        >
          <span>{showTable ? 'Скрыть таблицу 11 пар' : 'Показать сходимость 11 пар'}</span>
          {showTable ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
        </button>

        <Link
          to="/methodology#metric"
          className="inline-flex items-center gap-0.5 text-[11px] text-text-secondary hover:text-text-primary transition-colors"
        >
          <span>Формула ТЗ</span>
          <ExternalLink className="w-2.5 h-2.5" />
        </Link>
      </div>

      {/* 11 Pairs Table */}
      {showTable && (
        <div className="border border-slate-200 rounded-lg overflow-x-auto max-h-48 overflow-y-auto bg-white animate-in fade-in">
          <table className="w-full text-[10px] text-left">
            <thead className="bg-slate-100 text-text-secondary sticky top-0 border-b border-slate-200">
              <tr>
                <th className="py-1 px-1.5">Пара</th>
                <th className="py-1 px-1.5 text-right">Затопл. (га)</th>
                <th className="py-1 px-1.5 text-right">Эталон (га)</th>
                <th className="py-1 px-1.5 text-right">q_flood</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {metrics.details.map((d) => (
                <tr
                  key={d.pair_id}
                  className={d.pair_id === activePairId ? 'bg-sky-50 font-semibold' : 'hover:bg-slate-50'}
                >
                  <td className="py-1 px-1.5 truncate max-w-[120px]" title={d.pair_id}>
                    {d.pair_id.replace('flood_', '').replace('baseline_', 'base_')}
                  </td>
                  <td className="py-1 px-1.5 text-right">{d.flood_sub_ha}</td>
                  <td className="py-1 px-1.5 text-right">{d.flood_ref_ha}</td>
                  <td className="py-1 px-1.5 text-right font-mono text-[#0284C7]">{d.q_flood.toFixed(3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
