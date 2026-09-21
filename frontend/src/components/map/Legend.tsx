import React from 'react';
import { ChevronUp, Eye, X } from 'lucide-react';
import { WATER_COLORS } from '../../lib/colors';
import { formatKm2 } from '../../lib/format';
import { useUiStore } from '../../store/uiStore';

interface LegendProps {
  aoiKm2?: number;
}

export const Legend: React.FC<LegendProps> = ({ aoiKm2 = 1245 }) => {
  const { showLegend, setShowLegend } = useUiStore();

  if (!showLegend) {
    return (
      <button
        onClick={() => setShowLegend(true)}
        className="bg-white/95 backdrop-blur-sm border border-[#EAECF0] rounded-xl px-3 py-1.5 shadow-floating text-xs font-semibold text-text-secondary hover:text-text-primary flex items-center gap-2 transition-all hover:bg-white select-none hover:scale-105 cursor-pointer"
        title="Показать легенду"
      >
        <span
          className="w-2.5 h-2.5 rounded-xs"
          style={{ backgroundColor: WATER_COLORS.flood.fillColor }}
        />
        <span>Легенда</span>
        <ChevronUp className="w-3.5 h-3.5 text-text-muted" />
      </button>
    );
  }

  return (
    <div className="bg-white/95 backdrop-blur-sm border border-[#EAECF0] rounded-xl p-3 shadow-floating w-56 text-xs select-none">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-1.5">
          <Eye className="w-3.5 h-3.5 text-[#0EA5E9]" />
          <span className="font-semibold text-text-primary text-[12px]">Легенда</span>
        </div>
        <button
          onClick={() => setShowLegend(false)}
          className="p-1 text-text-muted hover:text-text-primary hover:bg-[#F1F5F9] rounded-md transition-colors cursor-pointer"
          title="Скрыть легенду"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>

      <div className="space-y-1.5">
        <div className="flex items-center gap-2">
          <span
            className="w-3 h-3 rounded-xs shrink-0 border"
            style={{
              backgroundColor: WATER_COLORS.flood.fillColor,
              borderColor: WATER_COLORS.flood.color,
            }}
          />
          <span className="text-text-secondary text-[11px]">Новое затопление (flood)</span>
        </div>

        <div className="flex items-center gap-2">
          <span
            className="w-3 h-3 rounded-xs shrink-0"
            style={{ backgroundColor: WATER_COLORS.water_peak.fillColor }}
          />
          <span className="text-text-secondary text-[11px]">Вода на пик</span>
        </div>

        <div className="flex items-center gap-2">
          <span
            className="w-3 h-3 rounded-xs shrink-0"
            style={{ backgroundColor: WATER_COLORS.water_pre.fillColor }}
          />
          <span className="text-text-secondary text-[11px]">Вода на до</span>
        </div>

        <div className="flex items-center gap-2">
          <span
            className="w-3 h-3 rounded-xs shrink-0"
            style={{ backgroundColor: WATER_COLORS.permanent.fillColor }}
          />
          <span className="text-text-secondary text-[11px]">Постоянная вода</span>
        </div>

        <div className="flex items-center gap-2">
          <span
            className="w-3 h-3 rounded-xs shrink-0 border border-dashed"
            style={{
              backgroundColor: 'rgba(167, 139, 250, 0.25)',
              borderColor: WATER_COLORS.receded.color,
            }}
          />
          <span className="text-text-secondary text-[11px]">Убыль воды</span>
        </div>
      </div>

      <div className="mt-2.5 pt-2 border-t border-[#F1F5F9] flex items-center justify-between text-[11px] text-text-muted">
        <span>Площадь AOI:</span>
        <span className="font-mono font-medium text-text-secondary">{formatKm2(aoiKm2, 0)}</span>
      </div>
    </div>
  );
};
