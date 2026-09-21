import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useUiStore } from '../../store/uiStore';
import { cn } from '../../lib/cn';

export const ModeSwitcher: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { activePairId } = useUiStore();

  const getActiveMode = (): 'map' | 'report' | 'compare' => {
    if (location.pathname.startsWith('/report')) return 'report';
    if (location.pathname.startsWith('/compare')) return 'compare';
    return 'map';
  };

  const currentMode = getActiveMode();

  const handleSwitch = (mode: 'map' | 'report' | 'compare') => {
    const pairId = activePairId || 'flood_2019_07_amur__blagoveshchensk';
    if (mode === 'map') {
      navigate(`/dashboard/${pairId}`);
    } else if (mode === 'report') {
      navigate(`/report/${pairId}`);
    } else if (mode === 'compare') {
      navigate(`/compare/${pairId}`);
    }
  };

  return (
    <div className="flex items-center bg-[#F1F5F9] p-1 rounded-lg border border-[#E2E8F0]">
      <button
        onClick={() => handleSwitch('map')}
        className={cn(
          'px-4 py-1.5 text-xs font-medium rounded-md transition-all',
          currentMode === 'map'
            ? 'bg-white text-text-primary shadow-sm'
            : 'text-text-secondary hover:text-text-primary'
        )}
      >
        Карта
      </button>
      <button
        onClick={() => handleSwitch('report')}
        className={cn(
          'px-4 py-1.5 text-xs font-medium rounded-md transition-all',
          currentMode === 'report'
            ? 'bg-white text-text-primary shadow-sm'
            : 'text-text-secondary hover:text-text-primary'
        )}
      >
        Отчёт
      </button>
      <button
        onClick={() => handleSwitch('compare')}
        className={cn(
          'px-4 py-1.5 text-xs font-medium rounded-md transition-all',
          currentMode === 'compare'
            ? 'bg-white text-text-primary shadow-sm'
            : 'text-text-secondary hover:text-text-primary'
        )}
      >
        Сравнение
      </button>
    </div>
  );
};
