import React from 'react';
import type { ReportData } from '../../types/domain';
import { formatHa, formatKm2 } from '../../lib/format';
import { ArrowUpRight } from 'lucide-react';

interface KpiCardsProps {
  report: ReportData | null;
  isLoading?: boolean;
}

export const KpiCards: React.FC<KpiCardsProps> = ({ report, isLoading = false }) => {
  if (isLoading || !report) {
    return (
      <div className="space-y-3">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-20 bg-slate-100 rounded-xl animate-pulse" />
        ))}
      </div>
    );
  }

  const aoiPercent = (report.share_of_aoi * 100).toFixed(2);

  return (
    <div className="space-y-3">
      {/* Карточка затопления */}
      <div className="bg-white border border-[#EAECF0] rounded-xl p-3.5 shadow-card relative pl-4 overflow-hidden">
        <div className="absolute left-0 top-0 bottom-0 w-1.5 bg-[#F97316]" />
        <div className="text-[11px] font-semibold text-text-muted tracking-wider uppercase">
          НОВОЕ ЗАТОПЛЕНИЕ
        </div>
        <div className="mt-1 flex items-baseline gap-2">
          <span className="font-mono text-2xl font-bold text-text-primary tracking-tight tabular-nums">
            {formatHa(report.flood_ha, 1)}
          </span>
        </div>
        <div className="text-xs text-text-secondary mt-1 flex items-center gap-1.5">
          <span>{formatKm2(report.flood_ha / 100, 2)}</span>
          <span className="text-text-muted">·</span>
          <span>{aoiPercent}% от AOI</span>
        </div>
        {report.water_gain_pct !== undefined && (
          <div className="mt-2 flex items-center gap-1 text-[11px] font-medium text-emerald-600">
            <ArrowUpRight className="w-3.5 h-3.5" />
            <span>+{report.water_gain_pct.toFixed(1)}% прирост зеркала воды</span>
          </div>
        )}
      </div>

      {/* Карточка воды на пик */}
      <div className="bg-white border border-[#EAECF0] rounded-xl p-3.5 shadow-card relative pl-4 overflow-hidden">
        <div className="absolute left-0 top-0 bottom-0 w-1.5 bg-[#06B6D4]" />
        <div className="text-[11px] font-semibold text-text-muted tracking-wider">
          Водное зеркало (пик)
        </div>
        <div className="mt-1 flex items-baseline gap-2">
          <span className="font-mono text-xl font-bold text-text-primary tabular-nums">
            {formatHa(report.water_peak_ha, 1)}
          </span>
          <span className="text-xs text-text-secondary">
            · {formatKm2(report.water_peak_ha / 100, 2)}
          </span>
        </div>
      </div>

      {/* Карточка воды до */}
      <div className="bg-white border border-[#EAECF0] rounded-xl p-3.5 shadow-card relative pl-4 overflow-hidden">
        <div className="absolute left-0 top-0 bottom-0 w-1.5 bg-[#60A5FA]" />
        <div className="text-[11px] font-semibold text-text-muted tracking-wider">
          Водное зеркало (до)
        </div>
        <div className="mt-1 flex items-baseline gap-2">
          <span className="font-mono text-xl font-bold text-text-primary tabular-nums">
            {formatHa(report.water_pre_ha, 1)}
          </span>
          <span className="text-xs text-text-secondary">
            · {formatKm2(report.water_pre_ha / 100, 2)}
          </span>
        </div>
      </div>

      {/* Карточка спада воды */}
      <div className="bg-white border border-[#EAECF0] rounded-xl p-3.5 shadow-card relative pl-4 overflow-hidden">
        <div className="absolute left-0 top-0 bottom-0 w-1.5 bg-[#A78BFA]" />
        <div className="text-[11px] font-semibold text-text-muted tracking-wider">
          Убыль воды
        </div>
        <div className="mt-1 flex items-baseline gap-2">
          <span className="font-mono text-xl font-bold text-text-primary tabular-nums">
            {formatHa(report.receded_ha ?? 0, 1)}
          </span>
        </div>
      </div>
    </div>
  );
};
