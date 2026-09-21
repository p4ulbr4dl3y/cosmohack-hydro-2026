import React from 'react';
import type { Pair } from '../../types/domain';
import { StatusBadge } from './StatusBadge';
import { formatNumber } from '../../lib/format';
import { cn } from '../../lib/cn';

interface PairCardProps {
  pair: Pair;
  isSelected: boolean;
  onSelect: (pair: Pair) => void;
}

function formatDateShort(d?: string): string {
  if (!d) return '';
  const parts = d.split('-');
  if (parts.length === 3) {
    return `${parts[2]}.${parts[1]}`;
  }
  return d;
}

export const PairCard: React.FC<PairCardProps> = ({ pair, isSelected, onSelect }) => {
  const [eventName, aoiPart] = pair.pair_id.split('__');
  const displayName = pair.aoi_name ? pair.aoi_name.split('—')[0].trim() : (aoiPart || '');

  const dateSarPre = formatDateShort(pair.date_pre_sar);
  const dateSarPeak = formatDateShort(pair.date_peak_sar);
  const dateOptPeak = formatDateShort(pair.date_peak_opt || pair.date_pre_opt);

  const sarStr = dateSarPre && dateSarPeak ? `SAR: ${dateSarPre} → ${dateSarPeak}` : '';
  const optStr = dateOptPeak ? `MSI: ${dateOptPeak}` : '';
  const dateLine = [sarStr, optStr].filter(Boolean).join(' · ');

  const areaText =
    pair.status === 'no_optical' && !pair.aoi_km2
      ? '—'
      : (pair as any).flood_ha
      ? `${formatNumber((pair as any).flood_ha, 0)} га`
      : '—';

  return (
    <div
      onClick={() => onSelect(pair)}
      className={cn(
        'p-3 rounded-xl border transition-all cursor-pointer select-none text-left relative',
        isSelected
          ? 'bg-[#F0F9FF] border-[#0EA5E9] shadow-sm'
          : 'bg-white border-[#EAECF0] hover:border-[#CBD5E1] hover:bg-[#F8FAFC]'
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="font-semibold text-xs text-text-primary truncate">
              {eventName}
            </span>
            <span className="text-text-muted text-xs">·</span>
            <span className="text-text-secondary text-xs truncate">
              {displayName}
            </span>
          </div>

          <div className="text-[11px] text-text-muted mt-1 truncate">
            {dateLine || 'Наблюдения Sentinel-1/2'}
          </div>
        </div>

        <div className="text-right shrink-0">
          <span className="font-mono font-medium text-xs text-text-primary tabular-nums">
            {areaText}
          </span>
        </div>
      </div>

      <div className="mt-2.5 flex items-center">
        <StatusBadge status={pair.status || 'active'} />
      </div>
    </div>
  );
};
