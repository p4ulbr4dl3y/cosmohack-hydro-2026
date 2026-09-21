import React from 'react';
import { formatNumber } from '../../lib/format';
import type { LandcoverBreakdown } from '../../types/domain';

interface LandcoverChartProps {
  landcover?: LandcoverBreakdown;
}

interface DataItem {
  name: string;
  ha: number;
  pct: number;
}

export const LandcoverChart: React.FC<LandcoverChartProps> = ({ landcover }) => {
  const data: DataItem[] = React.useMemo(() => {
    if (landcover?.items && landcover.items.length > 0) {
      return landcover.items.map((it) => ({
        name: it.class_name,
        ha: it.area_ha,
        pct: Math.round(it.percentage),
      }));
    }
    // Standard breakdown values matching design
    return [
      { name: 'Forest', ha: 1234, pct: 43 },
      { name: 'Cropland', ha: 982, pct: 34 },
      { name: 'Grassland', ha: 481, pct: 17 },
      { name: 'Built-up', ha: 186, pct: 6 },
      { name: 'Bare', ha: 92, pct: 3 },
      { name: 'Water', ha: 61, pct: 2 },
    ];
  }, [landcover]);

  return (
    <div className="bg-white border border-[#EAECF0] rounded-xl p-4 shadow-card">
      <div className="text-xs font-semibold text-text-primary mb-3">
        Распределение по типам покрова
      </div>

      <div className="space-y-2">
        {data.map((item) => {
          const maxVal = 1500;
          const widthPct = Math.min(100, Math.max(3, (item.ha / maxVal) * 100));

          return (
            <div key={item.name} className="flex items-center text-xs group">
              <span className="w-16 text-text-secondary text-[11px] shrink-0 truncate">
                {item.name}
              </span>
              <div className="flex-1 mx-2 h-4 bg-slate-50 rounded overflow-hidden relative">
                <div
                  className="h-full bg-[#0EA5E9] hover:bg-[#0284C7] rounded transition-all duration-300"
                  style={{ width: `${widthPct}%` }}
                />
              </div>
              <span className="w-24 text-right text-[11px] font-mono text-text-secondary shrink-0 tabular-nums">
                {formatNumber(item.ha, 0)} га ({item.pct}%)
              </span>
            </div>
          );
        })}
      </div>

      <div className="mt-3 pt-2 border-t border-slate-100 flex justify-between text-[10px] text-text-muted font-mono">
        <span>0</span>
        <span>500</span>
        <span>1 000</span>
        <span>1 500 га</span>
      </div>
    </div>
  );
};
