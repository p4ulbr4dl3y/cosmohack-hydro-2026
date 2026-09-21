import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Play, ArrowRight, Menu, X, Map, BookOpen, Terminal } from 'lucide-react';
import { MapContainer } from '../components/map/MapContainer';
import { apiClient } from '../api/client';
import type { Pair } from '../types/domain';

export const Landing: React.FC = () => {
  const navigate = useNavigate();
  const [previewPair, setPreviewPair] = useState<Pair | null>(null);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    apiClient.fetchPairs().then((pairs) => {
      const defaultPair = pairs.find((p) => p.pair_id === 'flood_2019_07_amur__blagoveshchensk') || pairs[0];
      if (defaultPair) setPreviewPair(defaultPair);
    }).catch(console.error);
  }, []);

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

          {/* Hero Right Column: Inactive Real Map Card */}
          <div className="lg:col-span-6">
            <div className="bg-white border border-[#EAECF0] rounded-2xl shadow-floating overflow-hidden h-[320px] sm:h-[440px] relative select-none">
              {/* Real Leaflet Map with all real layers, completely non-interactive */}
              <div className="w-full h-full pointer-events-none select-none">
                <MapContainer
                  currentPair={previewPair}
                  interactive={false}
                  showControls={false}
                  className="w-full h-full"
                />
              </div>

              {/* Floating Real KPI Badge */}
              <div className="absolute top-3 right-3 sm:top-4 sm:right-4 bg-white/95 backdrop-blur-sm rounded-xl p-2.5 sm:p-3 shadow-floating border border-[#EAECF0] text-left pointer-events-none">
                <div className="flex items-center gap-1.5">
                  <span className="w-2 sm:w-2.5 h-2 sm:h-2.5 rounded-full bg-[#F97316]" />
                  <span className="font-mono font-bold text-xs sm:text-sm text-text-primary">
                    2 847,3 га
                  </span>
                </div>
                <div className="text-[10px] sm:text-[11px] text-text-secondary mt-0.5 font-medium">
                  нового затопления
                </div>
                <div className="text-[9px] sm:text-[10px] text-text-muted mt-0.5 font-mono">
                  {previewPair ? `${previewPair.date_pre_sar || '12.07'} -> ${previewPair.date_peak_sar || '14.07.2019'}` : '14.07.2019'}
                </div>
              </div>

              {/* Water Classes Legend Strip at Bottom Left */}
              <div className="absolute bottom-3 left-3 sm:bottom-4 sm:left-4 bg-white/90 backdrop-blur-xs border border-[#EAECF0] rounded-lg px-2 sm:px-3 py-1 sm:py-1.5 shadow-sm text-[10px] sm:text-[11px] flex items-center gap-2 sm:gap-3 pointer-events-none">
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

              {/* Sensor indicator pill (Top Left) */}
              <div className="absolute top-3 left-3 sm:top-4 sm:left-4 bg-white/95 backdrop-blur-sm border border-[#EAECF0] rounded-full px-2.5 py-0.5 sm:py-1 shadow-sm text-[10px] sm:text-[11px] font-mono font-medium text-text-secondary pointer-events-none flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                <span>Sentinel-1 GIS</span>
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
