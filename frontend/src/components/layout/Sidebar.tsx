import React, { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import type { Pair } from '../../types/domain';
import { PairCard } from '../controls/PairCard';
import { useUiStore } from '../../store/uiStore';
import { cn } from '../../lib/cn';
import { Search } from 'lucide-react';

interface SidebarProps {
  pairs: Pair[];
  isLoading?: boolean;
  onSelectPair?: (pair: Pair) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ pairs, isLoading = false, onSelectPair }) => {
  const navigate = useNavigate();
  const {
    activePairId,
    setActivePairId,
    filterKind,
    setFilterKind,
    filterOnlyOptical,
    setFilterOnlyOptical,
    sortBy,
    setSortBy,
    searchQuery,
    setSearchQuery,
  } = useUiStore();

  const floodCount = useMemo(() => pairs.filter((p) => p.event_kind !== 'baseline').length, [pairs]);
  const baselineCount = useMemo(() => pairs.filter((p) => p.event_kind === 'baseline').length, [pairs]);

  const filteredPairs = useMemo(() => {
    return pairs
      .filter((pair) => {
        if (filterKind === 'flood' && pair.event_kind === 'baseline') return false;
        if (filterKind === 'baseline' && pair.event_kind !== 'baseline') return false;
        if (filterOnlyOptical && !pair.has_optical) return false;
        if (searchQuery) {
          const q = searchQuery.toLowerCase();
          const matchId = pair.pair_id.toLowerCase().includes(q);
          const matchAoi = pair.aoi_name?.toLowerCase().includes(q);
          const matchEvent = pair.event_name?.toLowerCase().includes(q);
          if (!matchId && !matchAoi && !matchEvent) return false;
        }
        return true;
      })
      .sort((a, b) => {
        if (sortBy === 'area') {
          // Пары без измеренной площади уходят в конец, а не встают в начало списка
          // наравне с нулевыми значениями.
          const areaA = a.flood_ha;
          const areaB = b.flood_ha;
          if (areaA === undefined && areaB === undefined) return 0;
          if (areaA === undefined) return 1;
          if (areaB === undefined) return -1;
          return areaB - areaA;
        }
        if (sortBy === 'name') {
          return a.aoi_name.localeCompare(b.aoi_name);
        }
        // По умолчанию по убыванию даты
        return (b.date_peak_sar || '').localeCompare(a.date_peak_sar || '');
      });
  }, [pairs, filterKind, filterOnlyOptical, searchQuery, sortBy]);

  const handleSelectPair = (pair: Pair) => {
    setActivePairId(pair.pair_id);
    if (onSelectPair) onSelectPair(pair);
    navigate(`/dashboard/${pair.pair_id}`);
  };

  return (
    <aside className="w-full lg:w-80 bg-surface border-r border-border flex flex-col h-full shrink-0 select-none z-20">
      {/* Верхняя секция */}
      <div className="p-4 border-b border-border space-y-3.5">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-bold text-text-muted tracking-wider uppercase">
            НАБЛЮДЕНИЯ
          </span>
          <span className="text-xs text-text-muted font-mono">
            {filteredPairs.length} из {pairs.length}
          </span>
        </div>

        {/* Плашки фильтров */}
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => setFilterKind('all')}
            className={cn(
              'px-3 py-1 rounded-full text-xs font-medium transition-colors',
              filterKind === 'all'
                ? 'bg-[#0EA5E9] text-white shadow-xs'
                : 'bg-[#F1F5F9] text-text-secondary hover:bg-[#E2E8F0]'
            )}
          >
            Все
          </button>
          <button
            onClick={() => setFilterKind('flood')}
            className={cn(
              'px-3 py-1 rounded-full text-xs font-medium transition-colors',
              filterKind === 'flood'
                ? 'bg-[#0EA5E9] text-white shadow-xs'
                : 'bg-[#F1F5F9] text-text-secondary hover:bg-[#E2E8F0]'
            )}
          >
            События ({floodCount || 8})
          </button>
          <button
            onClick={() => setFilterKind('baseline')}
            className={cn(
              'px-3 py-1 rounded-full text-xs font-medium transition-colors',
              filterKind === 'baseline'
                ? 'bg-[#0EA5E9] text-white shadow-xs'
                : 'bg-[#F1F5F9] text-text-secondary hover:bg-[#E2E8F0]'
            )}
          >
            Межень ({baselineCount || 3})
          </button>
        </div>

        {/* Чекбокс "Только с оптикой" */}
        <div className="flex items-center justify-between pt-0.5">
          <label className="flex items-center gap-2 cursor-pointer text-xs text-text-secondary hover:text-text-primary">
            <input
              type="checkbox"
              checked={filterOnlyOptical}
              onChange={(e) => setFilterOnlyOptical(e.target.checked)}
              className="w-4 h-4 rounded border-border text-accent focus:ring-accent accent-accent cursor-pointer"
            />
            <span>Только с оптикой</span>
          </label>
        </div>

        {/* Сортировка и поиск */}
        <div className="flex items-center justify-between gap-2 pt-1 text-xs">
          <span className="text-text-muted shrink-0">Сортировка:</span>
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as any)}
            className="flex-1 bg-white border border-border rounded-md px-2 py-1 text-xs text-text-primary focus:outline-none focus:border-accent cursor-pointer"
          >
            <option value="date">по дате</option>
            <option value="area">по площади</option>
            <option value="name">по району</option>
          </select>
        </div>

        {/* Быстрый поиск */}
        <div className="relative">
          <Search className="w-3.5 h-3.5 text-text-muted absolute left-2.5 top-2.5 pointer-events-none" />
          <input
            type="text"
            placeholder="Поиск по району или дате..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-[#F8FAFC] border border-border rounded-lg pl-8 pr-3 py-1.5 text-xs text-text-primary placeholder:text-text-muted focus:bg-white focus:outline-none focus:border-accent"
          />
        </div>
      </div>

      {/* Список карточек */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {isLoading ? (
          <div className="space-y-2 p-2">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-20 bg-slate-100 rounded-xl animate-pulse" />
            ))}
          </div>
        ) : filteredPairs.length === 0 ? (
          <div className="py-12 text-center text-text-muted text-xs">
            Нет наблюдений по выбранным фильтрам
          </div>
        ) : (
          filteredPairs.map((pair) => (
            <PairCard
              key={pair.pair_id}
              pair={pair}
              isSelected={pair.pair_id === activePairId}
              onSelect={handleSelectPair}
            />
          ))
        )}
      </div>
    </aside>
  );
};
