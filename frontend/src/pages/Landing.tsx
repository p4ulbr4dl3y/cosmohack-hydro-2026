import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Play,
  ArrowRight,
  Menu,
  X,
  Map,
  BookOpen,
  Terminal,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
} from 'lucide-react';
import { MapContainer } from '../components/map/MapContainer';
import { apiClient } from '../api/client';
import type { Pair } from '../types/domain';

const PAIR_NAMES: Record<string, { city: string; title: string; event: string }> = {
  'baseline_2018_09_low__blagoveshchensk': { city: 'Благовещенск', title: 'Благовещенск, р. Амур', event: 'Базовый межень' },
  'baseline_2018_09_low__konstantinovka': { city: 'Константиновка', title: 'Константиновка, р. Амур', event: 'Базовый межень' },
  'baseline_2018_09_low__svobodny': { city: 'Свободный', title: 'Свободный, р. Зея', event: 'Базовый межень' },
  'flood_2019_07_amur__belogorsk': { city: 'Белогорск', title: 'Белогорск, р. Томь', event: 'Локальный паводок' },
  'flood_2019_07_amur__blagoveshchensk': { city: 'Благовещенск', title: 'Благовещенск, р. Амур', event: 'Паводок 2019' },
  'flood_2019_07_amur__konstantinovka': { city: 'Константиновка', title: 'Константиновка, р. Амур', event: 'Паводок 2019' },
  'flood_2019_07_amur__svobodny': { city: 'Свободный', title: 'Свободный, р. Зея', event: 'Паводок 2019' },
  'flood_2021_06_amur__blagoveshchensk': { city: 'Благовещенск', title: 'Благовещенск, р. Амур', event: 'Паводок 2021 (пик)' },
  'flood_2021_06_amur__konstantinovka': { city: 'Константиновка', title: 'Константиновка, р. Амур', event: 'Паводок 2021' },
  'flood_2021_06_amur__poyarkovo': { city: 'Поярково', title: 'Поярково, р. Амур', event: 'Паводок 2021' },
  'flood_2021_08_zeya__svobodny': { city: 'Свободный', title: 'Свободный, р. Зея', event: 'Паводок 2021 (Зея)' },
};

const PAIR_FLOOD_STATS: Record<string, { flood_ha: number; water_peak_ha: number }> = {
  'baseline_2018_09_low__blagoveshchensk': { flood_ha: 328.4, water_peak_ha: 8524.8 },
  'baseline_2018_09_low__konstantinovka': { flood_ha: 332.2, water_peak_ha: 6425.5 },
  'baseline_2018_09_low__svobodny': { flood_ha: 175.5, water_peak_ha: 4540.9 },
  'flood_2019_07_amur__belogorsk': { flood_ha: 69.6, water_peak_ha: 767.0 },
  'flood_2019_07_amur__blagoveshchensk': { flood_ha: 996.4, water_peak_ha: 9189.0 },
  'flood_2019_07_amur__konstantinovka': { flood_ha: 722.3, water_peak_ha: 7052.8 },
  'flood_2019_07_amur__svobodny': { flood_ha: 556.0, water_peak_ha: 4999.7 },
  'flood_2021_06_amur__blagoveshchensk': { flood_ha: 3745.0, water_peak_ha: 11824.0 },
  'flood_2021_06_amur__konstantinovka': { flood_ha: 4863.4, water_peak_ha: 10746.2 },
  'flood_2021_06_amur__poyarkovo': { flood_ha: 2046.2, water_peak_ha: 6883.8 },
  'flood_2021_08_zeya__svobodny': { flood_ha: 7496.9, water_peak_ha: 12292.9 },
};

export const Landing: React.FC = () => {
  const navigate = useNavigate();
  const [pairs, setPairs] = useState<Pair[]>([]);
  const [slideIndex, setSlideIndex] = useState(0);
  const [isPaused, setIsPaused] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    apiClient.fetchPairs().then((loadedPairs) => {
      if (loadedPairs && loadedPairs.length > 0) {
        setPairs(loadedPairs);
        const idx = loadedPairs.findIndex((p) => p.pair_id === 'flood_2019_07_amur__blagoveshchensk');
        if (idx !== -1) setSlideIndex(idx);
      }
    }).catch(console.error);
  }, []);

  // Auto-advance slideshow every 4.5 seconds unless user hovers
  useEffect(() => {
    if (isPaused || pairs.length <= 1) return;
    const timer = setInterval(() => {
      setSlideIndex((prev) => (prev + 1) % pairs.length);
    }, 4500);
    return () => clearInterval(timer);
  }, [isPaused, pairs.length]);

  const currentPair = pairs[slideIndex] || null;
  const currentInfo = currentPair
    ? PAIR_NAMES[currentPair.pair_id] || {
        city: currentPair.aoi_name || 'Амурская обл.',
        title: currentPair.pair_id,
        event: currentPair.event_name || 'Наблюдение',
      }
    : null;
  const currentStats = currentPair
    ? PAIR_FLOOD_STATS[currentPair.pair_id] || {
        flood_ha: (currentPair as any).flood_ha || 996.4,
        water_peak_ha: 2847.3,
      }
    : { flood_ha: 996.4, water_peak_ha: 2847.3 };

  const prevSlide = () => {
    setSlideIndex((prev) => (prev - 1 + pairs.length) % pairs.length);
  };
  const nextSlide = () => {
    setSlideIndex((prev) => (prev + 1) % pairs.length);
  };

  return (
    <div className="min-h-screen bg-[#FAFBFC] text-text-primary flex flex-col font-sans">
      {/* Topbar */}
      <header className="sticky top-0 z-40 bg-white/95 backdrop-blur-sm border-b border-[#EAECF0] px-4 sm:px-8 h-16 flex items-center justify-between">
        <div className="flex items-center gap-4 sm:gap-8">
          {/* Mobile Hamburger Toggle */}
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="p-1.5 rounded-lg border border-border text-text-secondary hover:text-text-primary hover:bg-slate-50 md:hidden transition-colors"
            title="Меню навигации"
            aria-label="Toggle menu"
          >
            {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>

          <Link to="/" className="flex items-center gap-2.5">
            <img src="/icons/logo.png" alt="HydroWatch" className="w-7 h-7 sm:w-8 sm:h-8 object-contain" />
            <span className="font-bold text-lg sm:text-xl tracking-tight text-text-primary">HydroWatch</span>
            <span className="text-text-muted text-sm sm:text-base font-normal">Amur</span>
          </Link>

          <nav className="hidden md:flex items-center gap-6 text-sm font-medium">
            <Link
              to="/dashboard"
              className="text-text-secondary hover:text-text-primary transition-colors py-5"
            >
              Дашборд
            </Link>
            <Link
              to="/methodology"
              className="text-text-secondary hover:text-text-primary transition-colors py-5"
            >
              Методика
            </Link>
            <Link
              to="/api-docs"
              className="text-text-secondary hover:text-text-primary transition-colors py-5"
            >
              API
            </Link>
            <a
              href="https://github.com/p4ulbr4dl3y/cosmohack-hydro-2026"
              target="_blank"
              rel="noreferrer"
              className="text-text-secondary hover:text-text-primary transition-colors py-5"
            >
              GitHub
            </a>
          </nav>
        </div>

        <div className="flex items-center gap-2 sm:gap-3">
          <Link
            to="/api-docs"
            className="hidden sm:inline-block px-3.5 py-2 border border-[#EAECF0] bg-white hover:bg-[#F8FAFC] text-text-primary text-xs font-medium rounded-lg transition-colors shadow-2xs"
          >
            Документация
          </Link>
          <Link
            to="/dashboard"
            className="px-3 sm:px-4 py-2 bg-[#0EA5E9] hover:bg-[#0284C7] text-white text-xs font-semibold rounded-lg transition-colors flex items-center gap-1.5 shadow-xs"
          >
            <span>Открыть карту</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        {/* Mobile Navigation Drawer */}
        {mobileMenuOpen && (
          <div className="md:hidden absolute top-16 left-0 right-0 bg-white/98 backdrop-blur-md border-b border-[#EAECF0] shadow-xl p-4 z-50 animate-in slide-in-from-top-2 duration-150">
            <div className="space-y-1">
              <Link
                to="/dashboard"
                onClick={() => setMobileMenuOpen(false)}
                className="flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-xs font-medium text-text-secondary hover:bg-slate-50 hover:text-text-primary transition-colors"
              >
                <Map className="w-4 h-4 text-[#0EA5E9]" />
                <span>Дашборд с картой</span>
              </Link>
              <Link
                to="/methodology"
                onClick={() => setMobileMenuOpen(false)}
                className="flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-xs font-medium text-text-secondary hover:bg-slate-50 hover:text-text-primary transition-colors"
              >
                <BookOpen className="w-4 h-4 text-[#0EA5E9]" />
                <span>Методика вычислений</span>
              </Link>
              <Link
                to="/api-docs"
                onClick={() => setMobileMenuOpen(false)}
                className="flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-xs font-medium text-text-secondary hover:bg-slate-50 hover:text-text-primary transition-colors"
              >
                <Terminal className="w-4 h-4 text-[#0EA5E9]" />
                <span>REST API Документация</span>
              </Link>
              <a
                href="https://github.com/p4ulbr4dl3y/cosmohack-hydro-2026"
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-xs font-medium text-text-secondary hover:bg-slate-50 hover:text-text-primary transition-colors"
              >
                <span>GitHub репозиторий</span>
              </a>
            </div>
          </div>
        )}
      </header>

      {/* Main Container */}
      <main className="flex-1 max-w-7xl mx-auto px-4 sm:px-6 py-8 sm:py-12 w-full space-y-12 sm:space-y-16">
        {/* Hero Section */}
        <section className="grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-12 items-center">
          {/* Hero Left Column */}
          <div className="lg:col-span-6 space-y-5 sm:space-y-6">
            <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#E0F2FE] text-[#0284C7] text-xs font-semibold">
              <span>КосмоХакатон 2026</span>
            </div>

            <h1 className="text-3xl sm:text-4xl md:text-5xl font-extrabold text-[#0F172A] leading-tight tracking-tight">
              Мониторинг наводнений, который не зависит от облаков
            </h1>

            <p className="text-text-secondary text-sm sm:text-base leading-relaxed max-w-lg">
              Sentinel-1 SAR + Sentinel-2 MSI. Зона нового затопления и водное зеркало на две даты — за секунды, а не дни. Амурская область, 11 пар наблюдений.
            </p>

            <div className="flex flex-wrap items-center gap-3 pt-2">
              <Link
                to="/dashboard/flood_2019_07_amur__blagoveshchensk"
                className="px-5 sm:px-6 py-2.5 sm:py-3 bg-[#0EA5E9] hover:bg-[#0284C7] text-white text-xs sm:text-sm font-semibold rounded-xl transition-all shadow-sm flex items-center gap-2 cursor-pointer"
              >
                <span>Запустить анализ</span>
                <ArrowRight className="w-4 h-4" />
              </Link>

              <button
                onClick={() => navigate('/dashboard/flood_2019_07_amur__blagoveshchensk')}
                className="px-4 sm:px-5 py-2.5 sm:py-3 border border-[#EAECF0] bg-white hover:bg-[#F8FAFC] text-text-primary text-xs sm:text-sm font-medium rounded-xl transition-colors flex items-center gap-2 shadow-2xs cursor-pointer"
              >
                <Play className="w-4 h-4 fill-[#0EA5E9] text-[#0EA5E9]" />
                <span>Смотреть демо</span>
              </button>
            </div>

            <div className="pt-2 flex flex-wrap items-center gap-2 sm:gap-3 text-xs text-text-muted font-mono">
              <span>10 м/пиксель</span>
              <span>•</span>
              <span>EPSG:32652</span>
              <span>•</span>
              <span>REST API</span>
              <span>•</span>
              <span>Docker</span>
            </div>
          </div>

          {/* Hero Right Column: Interactive Location Slideshow Card */}
          <div className="lg:col-span-6">
            <div
              className="group bg-white border border-[#EAECF0] rounded-2xl shadow-floating overflow-hidden h-[340px] sm:h-[460px] relative select-none transition-all"
              onMouseEnter={() => setIsPaused(true)}
              onMouseLeave={() => setIsPaused(false)}
            >
              {/* Real Leaflet Map with all real layers */}
              <div className="w-full h-full pointer-events-none select-none">
                <MapContainer
                  currentPair={currentPair}
                  interactive={false}
                  showControls={false}
                  className="w-full h-full"
                />
              </div>

              {/* Location Badge (Top Left) */}
              <div className="absolute top-3 left-3 sm:top-4 sm:left-4 z-10 flex flex-col gap-1 pointer-events-none">
                <div className="bg-white/95 backdrop-blur-sm border border-[#EAECF0] rounded-full px-3 py-1 shadow-sm text-xs font-semibold text-text-primary flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                  <span>{currentInfo?.city || 'Благовещенск'}</span>
                  <span className="text-[11px] font-mono font-normal text-text-muted">
                    {slideIndex + 1}/{pairs.length || 11}
                  </span>
                </div>
                <div className="bg-white/90 backdrop-blur-sm border border-[#EAECF0] rounded-md px-2 py-0.5 shadow-2xs text-[10px] font-mono text-text-secondary">
                  {currentInfo?.event || 'Паводок 2019'} · {currentPair?.sensor_sar || 'Sentinel-1'}
                </div>
              </div>

              {/* Floating Real KPI Badge (Top Right) */}
              <div className="absolute top-3 right-3 sm:top-4 sm:right-4 z-10 bg-white/95 backdrop-blur-sm rounded-xl p-2.5 sm:p-3 shadow-floating border border-[#EAECF0] text-left pointer-events-none">
                <div className="flex items-center gap-1.5">
                  <span className="w-2 sm:w-2.5 h-2 sm:h-2.5 rounded-full bg-[#F97316]" />
                  <span className="font-mono font-bold text-xs sm:text-sm md:text-base text-text-primary">
                    {currentStats.flood_ha.toLocaleString('ru-RU')} га
                  </span>
                </div>
                <div className="text-[10px] sm:text-[11px] text-text-secondary mt-0.5 font-medium">
                  {currentPair?.event_kind === 'baseline' ? 'водное зеркало межени' : 'нового затопления'}
                </div>
                <div className="text-[9px] sm:text-[10px] text-text-muted mt-0.5 font-mono">
                  {currentPair ? `${currentPair.date_pre_sar || '12.07'} → ${currentPair.date_peak_sar || '14.07.2019'}` : '14.07.2019'}
                </div>
              </div>

              {/* Slideshow Arrow Controls */}
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  prevSlide();
                }}
                className="absolute left-2.5 top-1/2 -translate-y-1/2 z-10 w-8 h-8 rounded-full bg-white/90 hover:bg-white text-text-primary shadow-md border border-[#EAECF0] flex items-center justify-center transition-all opacity-80 hover:opacity-100 hover:scale-105 cursor-pointer"
                title="Предыдущая местность"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  nextSlide();
                }}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 z-10 w-8 h-8 rounded-full bg-white/90 hover:bg-white text-text-primary shadow-md border border-[#EAECF0] flex items-center justify-center transition-all opacity-80 hover:opacity-100 hover:scale-105 cursor-pointer"
                title="Следующая местность"
              >
                <ChevronRight className="w-4 h-4" />
              </button>

              {/* Quick Jump to Dashboard (Hover Button) */}
              {currentPair && (
                <button
                  onClick={() => navigate(`/dashboard/${currentPair.pair_id}`)}
                  className="absolute bottom-12 sm:bottom-14 right-3 sm:right-4 z-10 opacity-0 group-hover:opacity-100 transition-all bg-[#0EA5E9] hover:bg-[#0284C7] text-white text-xs font-semibold px-3 py-1.5 rounded-lg shadow-md flex items-center gap-1.5 cursor-pointer"
                >
                  <span>Исследовать район</span>
                  <ExternalLink className="w-3.5 h-3.5" />
                </button>
              )}

              {/* Bottom Bar: Water Classes Legend Strip + Interactive Slide Indicator Dots */}
              <div className="absolute bottom-3 inset-x-3 sm:bottom-4 sm:inset-x-4 z-10 flex flex-wrap items-center justify-between gap-2 pointer-events-auto">
                <div className="bg-white/90 backdrop-blur-xs border border-[#EAECF0] rounded-lg px-2 sm:px-3 py-1 sm:py-1.5 shadow-sm text-[10px] sm:text-[11px] flex items-center gap-2 sm:gap-3 pointer-events-none">
                  <div className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-[#F97316]" />
                    <span className="text-text-secondary">Затопление</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-[#06B6D4]" />
                    <span className="text-text-secondary">Пик</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-[#60A5FA]" />
                    <span className="text-text-secondary">До</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-[#3B82F6]" />
                    <span className="text-text-secondary">Постоянная</span>
                  </div>
                </div>

                {/* Slideshow Pill Dots */}
                <div className="bg-white/90 backdrop-blur-xs border border-[#EAECF0] rounded-lg px-2 py-1.5 shadow-sm flex items-center gap-1.5">
                  {pairs.map((p, idx) => (
                    <button
                      key={p.pair_id}
                      onClick={() => setSlideIndex(idx)}
                      className={`h-1.5 rounded-full transition-all cursor-pointer ${
                        idx === slideIndex ? 'w-5 bg-[#0EA5E9]' : 'w-1.5 bg-slate-300 hover:bg-slate-400'
                      }`}
                      title={`${PAIR_NAMES[p.pair_id]?.city || p.aoi_name} (${PAIR_NAMES[p.pair_id]?.event || p.event_name})`}
                    />
                  ))}
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* 3 Cards Section: Проблема / Подход / Результат */}
        <section className="grid grid-cols-1 md:grid-cols-3 gap-4 sm:gap-6">
          {/* Card 1: Проблема */}
          <div className="bg-white border border-[#EAECF0] rounded-2xl p-5 sm:p-6 shadow-card hover:shadow-floating transition-shadow space-y-3 sm:space-y-4">
            <div className="w-10 h-10 sm:w-12 sm:h-12 rounded-2xl bg-rose-50 border border-rose-100 flex items-center justify-center">
              <img src="/icons/error.png" alt="Проблема" className="w-5 h-5 sm:w-6 sm:h-6 object-contain" />
            </div>
            <h3 className="text-lg sm:text-xl font-bold text-text-primary">Проблема</h3>
            <p className="text-text-secondary text-xs sm:text-sm leading-relaxed">
              Паводок приходит при сплошной облачности — оптика Sentinel-2 слепа именно тогда, когда нужна.
            </p>
          </div>

          {/* Card 2: Подход */}
          <div className="bg-white border border-[#EAECF0] rounded-2xl p-5 sm:p-6 shadow-card hover:shadow-floating transition-shadow space-y-3 sm:space-y-4">
            <div className="w-10 h-10 sm:w-12 sm:h-12 rounded-2xl bg-sky-50 border border-sky-100 flex items-center justify-center">
              <img src="/icons/sattelate.png" alt="Подход" className="w-5 h-5 sm:w-6 sm:h-6 object-contain" />
            </div>
            <h3 className="text-lg sm:text-xl font-bold text-text-primary">Подход</h3>
            <p className="text-text-secondary text-xs sm:text-sm leading-relaxed">
              SAR всепогоден, но неоднозначен: ветровая рябь, затопленный лес, асфальт. Совмещаем два канала — ошибки независимы.
            </p>
          </div>

          {/* Card 3: Результат */}
          <div className="bg-white border border-[#EAECF0] rounded-2xl p-5 sm:p-6 shadow-card hover:shadow-floating transition-shadow space-y-3 sm:space-y-4">
            <div className="w-10 h-10 sm:w-12 sm:h-12 rounded-2xl bg-emerald-50 border border-emerald-100 flex items-center justify-center">
              <img src="/icons/result.png" alt="Результат" className="w-5 h-5 sm:w-6 sm:h-6 object-contain" />
            </div>
            <h3 className="text-lg sm:text-xl font-bold text-text-primary">Результат</h3>
            <p className="text-text-secondary text-xs sm:text-sm leading-relaxed">
              Маска затопления, водное зеркало на две даты, авто-отчёт в га и км². Экспорт GeoJSON, Shapefile, CSV.
            </p>
          </div>
        </section>

        {/* Метрика Section */}
        <section className="bg-white border border-[#EAECF0] rounded-2xl p-6 sm:p-8 shadow-card space-y-6">
          <h2 className="text-xl sm:text-2xl font-bold text-text-primary">Метрика оценки решения</h2>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 sm:gap-6 py-2">
            <div className="border-l-2 border-slate-200 pl-3 sm:pl-4 space-y-1">
              <div className="font-mono text-2xl sm:text-3xl md:text-4xl font-extrabold text-text-primary tracking-tight">
                0,45
              </div>
              <div className="text-[11px] sm:text-xs text-text-secondary font-mono">
                вес Q_flood
              </div>
            </div>

            <div className="border-l-2 border-slate-200 pl-3 sm:pl-4 space-y-1">
              <div className="font-mono text-2xl sm:text-3xl md:text-4xl font-extrabold text-text-primary tracking-tight">
                0,25
              </div>
              <div className="text-[11px] sm:text-xs text-text-secondary font-mono">
                Q_water_peak
              </div>
            </div>

            <div className="border-l-2 border-slate-200 pl-3 sm:pl-4 space-y-1">
              <div className="font-mono text-2xl sm:text-3xl md:text-4xl font-extrabold text-text-primary tracking-tight">
                0,15
              </div>
              <div className="text-[11px] sm:text-xs text-text-secondary font-mono">
                Q_water_pre
              </div>
            </div>

            <div className="border-l-2 border-slate-200 pl-3 sm:pl-4 space-y-1">
              <div className="font-mono text-2xl sm:text-3xl md:text-4xl font-extrabold text-text-primary tracking-tight">
                0,15
              </div>
              <div className="text-[11px] sm:text-xs text-text-secondary font-mono">
                Spec_base
              </div>
            </div>
          </div>

          <div className="pt-4 border-t border-[#F1F5F9] font-mono text-xs text-text-secondary overflow-x-auto">
            Итоговый Score = 0.45·Q_flood + 0.25·Q_water_peak + 0.15·Q_water_pre + 0.15·Spec_base
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-[#EAECF0] bg-white py-6 sm:py-8 px-4 sm:px-8 mt-12 text-xs text-text-muted">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="space-y-1 text-center md:text-left">
            <div>© HydroWatch Amur, 2026.</div>
            <div>Данные Copernicus © ESA</div>
          </div>

          <div className="flex flex-wrap justify-center items-center gap-4 sm:gap-6">
            <Link to="/methodology" className="hover:text-text-primary transition-colors">
              Методика
            </Link>
            <Link to="/api-docs" className="hover:text-text-primary transition-colors">
              API Документация
            </Link>
            <Link to="/dashboard" className="hover:text-text-primary transition-colors">
              Карта
            </Link>
          </div>

          <div className="flex items-center gap-4">
            <a
              href="https://github.com/p4ulbr4dl3y/cosmohack-hydro-2026"
              target="_blank"
              rel="noreferrer"
              className="text-text-secondary hover:text-text-primary transition-colors"
            >
              GitHub
            </a>
            <span className="text-text-muted">·</span>
            <span className="text-text-secondary">Sentinel-1 / Sentinel-2</span>
          </div>
        </div>
      </footer>
    </div>
  );
};
