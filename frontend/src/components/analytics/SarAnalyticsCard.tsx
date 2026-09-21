import React from 'react';
import type { SARAnalytics } from '../../types/domain';
import { Radio, CloudSun, Trees } from 'lucide-react';

interface SarAnalyticsCardProps {
  sar: SARAnalytics | null;
  isLoading?: boolean;
}

export const SarAnalyticsCard: React.FC<SarAnalyticsCardProps> = ({ sar, isLoading }) => {
  if (isLoading) {
    return (
      <div className="bg-white border border-[#EAECF0] rounded-xl p-3.5 animate-pulse space-y-2">
        <div className="h-4 bg-slate-200 rounded w-1/2"></div>
        <div className="h-10 bg-slate-100 rounded"></div>
      </div>
    );
  }

  if (!sar) return null;

  return (
    <div className="bg-white border border-[#EAECF0] rounded-xl p-3.5 space-y-2.5 shadow-2xs">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <Radio className="w-4 h-4 text-indigo-600" />
          <span className="text-xs font-semibold text-text-primary">Радарная аналитика (Sentinel-1)</span>
        </div>
        {sar.cloud_penetration_verified && (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200">
            <CloudSun className="w-3 h-3" />
            <span>Сквозь облака 24/7</span>
          </span>
        )}
      </div>

      <div className="grid grid-cols-2 gap-2 text-[11px]">
        <div className="bg-slate-50 p-2 rounded-lg">
          <div className="text-[10px] text-slate-500">Контраст вода/суша</div>
          <div className="font-mono font-semibold text-slate-800 mt-0.5">
            +{sar.radar_contrast_db.toFixed(1)} дБ
          </div>
        </div>

        <div className="bg-slate-50 p-2 rounded-lg">
          <div className="text-[10px] text-slate-500">Кросс-поляризация (VH/VV)</div>
          <div className="font-mono font-semibold text-slate-800 mt-0.5">
            {sar.mean_vh_vv_ratio.toFixed(1)} дБ
          </div>
        </div>
      </div>

      {sar.double_bounce_fraction > 0 && (
        <div className="flex items-center justify-between p-2 bg-emerald-50/70 border border-emerald-200/60 rounded-lg text-xs">
          <div className="flex items-center gap-1.5 text-emerald-900 font-medium">
            <Trees className="w-3.5 h-3.5 text-emerald-600" />
            <span>Затопленный лес (Double-bounce):</span>
          </div>
          <span className="font-mono font-bold text-emerald-800">
            {(sar.double_bounce_fraction * 100).toFixed(1)}%
          </span>
        </div>
      )}
    </div>
  );
};
