import React, { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { RotateCw, CheckCircle2, Menu, X, Map, GitCompare, FileText, BookOpen, Terminal } from 'lucide-react';
import { ModeSwitcher } from '../controls/ModeSwitcher';
import { apiClient } from '../../api/client';
import { useUiStore } from '../../store/uiStore';

interface TopbarProps {
  onRefresh?: () => void;
  isRefreshing?: boolean;
}

export const Topbar: React.FC<TopbarProps> = ({ onRefresh, isRefreshing = false }) => {
  const [recomputing, setRecomputing] = useState(false);
  const [recomputeSuccess, setRecomputeSuccess] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const { activePairId } = useUiStore();
  const location = useLocation();

  const pairId = activePairId || 'flood_2019_07_amur__blagoveshchensk';

  const handleRecompute = async () => {
    setRecomputing(true);
    try {
      await apiClient.recompute();
      setRecomputeSuccess(true);
      if (onRefresh) onRefresh();
      setTimeout(() => setRecomputeSuccess(false), 3000);
    } catch (e) {
      console.error(e);
    } finally {
      setRecomputing(false);
    }
  };

  const navLinks = [
    { label: 'Карта (Дашборд)', to: `/dashboard/${pairId}`, icon: Map, active: location.pathname.startsWith('/dashboard') },
    { label: 'Сравнение до/пик', to: `/compare/${pairId}`, icon: GitCompare, active: location.pathname.startsWith('/compare') },
    { label: 'Аналитический отчёт', to: `/report/${pairId}`, icon: FileText, active: location.pathname.startsWith('/report') },
    { label: 'Методика', to: '/methodology', icon: BookOpen, active: location.pathname.startsWith('/methodology') },
    { label: 'API Документация', to: '/api-docs', icon: Terminal, active: location.pathname.startsWith('/api-docs') },
  ];

  return (
    <header className="h-14 bg-surface border-b border-border px-3 sm:px-4 flex items-center justify-between z-30 shrink-0 relative">
      {/* Brand & Mobile Hamburger */}
      <div className="flex items-center gap-2 sm:gap-3">
        <button
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          className="p-1.5 rounded-lg border border-border text-text-secondary hover:text-text-primary hover:bg-slate-50 md:hidden transition-colors"
          title="Меню навигации"
          aria-label="Toggle menu"
        >
          {mobileMenuOpen ? <X className="w-4 h-4" /> : <Menu className="w-4 h-4" />}
        </button>

        <Link to="/" className="flex items-center gap-2 group">
          <img src="/icons/logo.png" alt="HydroWatch" className="w-6 h-6 sm:w-7 sm:h-7 object-contain" />
          <span className="font-bold text-base sm:text-lg text-text-primary tracking-tight">HydroWatch</span>
          <span className="text-text-muted text-xs sm:text-sm font-normal">Amur</span>
        </Link>
        <span className="hidden sm:inline bg-[#E0F2FE] text-[#0284C7] rounded px-1.5 py-0.5 text-[10px] font-semibold tracking-wide uppercase">
          BETA
        </span>
      </div>

      {/* Mode Switcher on Desktop */}
      <div className="hidden md:flex items-center justify-center">
        <ModeSwitcher />
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2 sm:gap-3">
        {recomputeSuccess && (
          <div className="hidden sm:flex items-center gap-1 text-xs text-emerald-600 bg-emerald-50 px-2 py-1 rounded-md border border-emerald-200 animate-in fade-in duration-200">
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span className="hidden md:inline">Пересчитано (12,4 с)</span>
          </div>
        )}

        <button
          onClick={handleRecompute}
          disabled={recomputing}
          className="bg-[#0F172A] hover:bg-[#1E293B] text-white text-xs font-medium px-2.5 sm:px-3.5 py-2 rounded-lg transition-colors flex items-center gap-1.5 shadow-sm disabled:opacity-75 cursor-pointer"
          title="Инициировать оперативный пересчёт по новому снимку"
        >
          <RotateCw className={`w-3.5 h-3.5 ${recomputing ? 'animate-spin' : ''}`} />
          <span className="hidden sm:inline">
            {recomputing ? 'Пересчёт...' : 'Пересчитать'}
          </span>
          <span className="hidden xl:inline">
            {!recomputing && ' по новому наблюдению'}
          </span>
        </button>

        <button
          onClick={onRefresh}
          disabled={isRefreshing}
          title="Обновить данные"
          className="p-2 text-text-secondary hover:text-text-primary hover:bg-[#F1F5F9] rounded-lg border border-border transition-colors cursor-pointer"
        >
          <RotateCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Mobile Drawer Menu */}
      {mobileMenuOpen && (
        <div className="md:hidden absolute top-14 left-0 right-0 bg-white/98 backdrop-blur-md border-b border-border shadow-xl p-4 z-50 animate-in slide-in-from-top-2 duration-150">
          <div className="text-[11px] font-bold text-text-muted uppercase tracking-wider mb-2 px-1">
            Навигация по разделам
          </div>
          <div className="space-y-1">
            {navLinks.map((link) => {
              const Icon = link.icon;
              return (
                <Link
                  key={link.to}
                  to={link.to}
                  onClick={() => setMobileMenuOpen(false)}
                  className={`flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-xs font-medium transition-colors ${
                    link.active
                      ? 'bg-[#E0F2FE] text-[#0284C7] font-semibold'
                      : 'text-text-secondary hover:bg-slate-50 hover:text-text-primary'
                  }`}
                >
                  <Icon className="w-4 h-4 shrink-0" />
                  <span>{link.label}</span>
                </Link>
              );
            })}
          </div>

          <div className="pt-3 mt-3 border-t border-slate-100 flex items-center justify-between text-[11px] text-text-muted px-1 font-mono">
            <span>pair: {pairId.slice(0, 24)}...</span>
            <span className="bg-[#E0F2FE] text-[#0284C7] px-1.5 py-0.5 rounded text-[10px]">BETA</span>
          </div>
        </div>
      )}
    </header>
  );
};
