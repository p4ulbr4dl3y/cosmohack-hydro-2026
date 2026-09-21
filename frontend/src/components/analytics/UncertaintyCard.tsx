import React from 'react';
import type { FloodUncertainty } from '../../types/domain';
import { Activity, Info, ShieldAlert } from 'lucide-react';

interface UncertaintyCardProps {
  uncertainty: FloodUncertainty | null;
  isLoading?: boolean;
}

export const UncertaintyCard: React.FC<UncertaintyCardProps> = ({ uncertainty, isLoading }) => {
  if (isLoading) {
    return (
      <div className="bg-white border border-[#EAECF0] rounded-xl p-3.5 animate-pulse space-y-2">
        <div className="h-4 bg-slate-200 rounded w-1/2"></div>
        <div className="h-10 bg-slate-100 rounded"></div>
      </div>
    );
  }

  if (!uncertainty) return null;

  return (
    <div className="bg-white border border-[#EAECF0] rounded-xl p-3.5 space-y-2.5 shadow-2xs">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <Activity className="w-4 h-4 text-[#0EA5E9]" />
          <span className="text-xs font-semibold text-text-primary">Неопределенность (IPCC/Chave)</span>
        </div>
        <span className="text-[10px] font-bold text-sky-700 bg-sky-50 border border-sky-200 px-2 py-0.5 rounded-full">
          {Math.round(uncertainty.confidence_level * 100)}% ДИ
        </span>
      </div>

      <div className="space-y-1.5">
        <div className="flex items-baseline justify-between">
          <span className="text-xs text-text-secondary">Доверительный интервал:</span>
          <span className="text-xs font-mono font-bold text-slate-800">
            [{uncertainty.lower_bound_ha.toFixed(1)} … {uncertainty.upper_bound_ha.toFixed(1)}] га
          </span>
        </div>

        {/* Градиентная полоса визуализации интервала */}
        <div className="relative pt-1.5 pb-1">
          <div className="relative h-2.5 bg-slate-100 rounded-full overflow-hidden p-[1px] shadow-inner">
            {/* Непрерывная полоса градиентного распределения */}
            <div
              className="h-full rounded-full transition-all duration-300"
              style={{
                width: '100%',
                background:
                  'linear-gradient(90deg, rgba(186, 230, 253, 0.4) 0%, rgba(56, 189, 248, 0.8) 25%, #0284c7 50%, rgba(56, 189, 248, 0.8) 75%, rgba(186, 230, 253, 0.4) 100%)',
                boxShadow: '0 0 8px rgba(14, 165, 233, 0.25)',
              }}
            />
            {/* Маркер центральной оценки */}
            <div
              className="absolute top-0 bottom-0 left-1/2 -translate-x-1/2 w-1.5 bg-white border border-sky-600 rounded-xs shadow-xs"
              title={`Центральная оценка: ${uncertainty.area_ha.toFixed(1)} га`}
            />
          </div>

          {/* Значения границ интервала под полосой */}
          <div className="flex justify-between items-center text-[9px] text-slate-400 font-mono mt-1">
            <span>-{(uncertainty.margin_ha).toFixed(1)} га</span>
            <span className="text-sky-700 font-semibold bg-sky-50 px-1.5 py-0.5 rounded border border-sky-100">
              ±{uncertainty.relative_uncertainty_pct.toFixed(2)}%
            </span>
            <span>+{(uncertainty.margin_ha).toFixed(1)} га</span>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2 pt-1 border-t border-slate-100 text-[11px]">
          <div className="bg-slate-50 p-2 rounded-lg border border-slate-100">
            <div className="text-[10px] text-slate-500 flex items-center gap-1">
              <span>Автокорреляция ρ</span>
              <Info className="w-2.5 h-2.5 text-slate-400" />
            </div>
            <div className="font-mono font-semibold text-slate-800 mt-0.5">
              {uncertainty.spatial_correlation.toFixed(2)}
            </div>
          </div>
          <div className="bg-slate-50 p-2 rounded-lg border border-slate-100">
            <div className="text-[10px] text-slate-500 flex items-center gap-1">
              <span>Эффективный N<sub>eff</sub></span>
              <ShieldAlert className="w-2.5 h-2.5 text-slate-400" />
            </div>
            <div className="font-mono font-semibold text-slate-800 mt-0.5">
              {uncertainty.effective_n_pixels.toLocaleString()} px
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
