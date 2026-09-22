import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  ArrowRight,
  AlertTriangle,
  FileCode,
  FileText,
  Boxes,
  ExternalLink,
  Menu,
  X,
  Map,
  BookOpen,
  Terminal,
} from 'lucide-react';

export const Methodology: React.FC = () => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const pipelineSteps = [
    {
      num: '01',
      title: 'Сегментация SAR',
      desc: 'Порог Оцу по VV (-22...-12 дБ), фильтрация спекла, требование падения σ⁰ ≥ 3 дБ.',
    },
    {
      num: '02',
      title: 'Сегментация MSI',
      desc: 'MNDWI > 0,1 или AWEIsh > 0,0 при NDVI ≤ 0,3 — там, где оптика пригодна.',
    },
    {
      num: '03',
      title: 'Гидрологические фильтры',
      desc: 'slope ≤ 5°, HAND ≤ 25 м, GSW occurrence ≥ 80%, минимальная картируемая единица 25 пикселей (0,25 га).',
    },
    {
      num: '04',
      title: 'Сведение источников',
      desc: 'Приоритет консенсуса SAR и MSI, затем GSW. Сверка с продуктом оперативного картирования.',
    },
    {
      num: '05',
      title: 'Постобработка',
      desc: 'Морфология контуров, удаление изолированных объектов, сглаживание границ.',
    },
  ];

  const limitations = [
    {
      text: 'Затопленная растительность не включается в маску воды — под пологом леса водная поверхность не наблюдается ни в оптике, ни надёжно в радиолокации.',
    },
    {
      text: 'Разрыв SAR<->MSI достигает 5 суток — оптика не является «истиной» для радара.',
    },
    {
      text: 'Эталонная разметка построена автоматически и не проходила сплошную ручную верификацию.',
    },
    {
      text: 'HAND — признак-подсказка, а не жёсткий запрет: в дельтах, на поймах и ниже плотин он не работает.',
    },
  ];

  const dataSources = [
    { name: 'Sentinel-1 GRD', source: 'Copernicus / GEE', license: 'Copernicus' },
    { name: 'Sentinel-2 L2A', source: 'Copernicus / GEE', license: 'Copernicus' },
    { name: 'DEM GLO-30', source: 'Copernicus', license: 'Copernicus' },
    { name: 'GSW', source: 'JRC', license: 'Открытая' },
    { name: 'MERIT Hydro', source: 'HydroSHEDS', license: 'Открытая' },
    { name: 'OSM', source: 'OpenStreetMap', license: 'ODbL' },
  ];

  return (
    <div className="min-h-screen bg-[#FAFBFC] text-text-primary font-sans flex flex-col">
      {/* Верхняя панель */}
      <header className="sticky top-0 z-40 bg-white/95 backdrop-blur-sm border-b border-[#EAECF0] px-4 sm:px-8 h-16 flex items-center justify-between">
        <div className="flex items-center gap-4 sm:gap-8">
          {/* Мобильная кнопка-гамбургер */}
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="p-1.5 rounded-lg border border-border text-text-secondary hover:text-text-primary hover:bg-slate-50 md:hidden transition-colors"
            title="Меню навигации"
            aria-label="Переключить меню"
          >
            {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>

          <Link to="/" className="flex items-center gap-2.5">
            <img src="/icons/logo.png" alt="HydroWatch" className="w-7 h-7 sm:w-8 sm:h-8 object-contain" />
            <span className="font-bold text-lg sm:text-xl tracking-tight text-text-primary">HydroWatch</span>
            <span className="text-text-muted text-sm sm:text-base font-normal">Amur</span>
            <span className="bg-[#E0F2FE] text-[#0284C7] rounded px-1.5 py-0.5 text-[10px] font-semibold tracking-wide uppercase">
              BETA
            </span>
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
              className="text-[#0EA5E9] border-b-2 border-[#0EA5E9] py-5 font-semibold"
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

        {/* Мобильное навигационное меню */}
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
                className="flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-xs font-semibold text-[#0284C7] bg-[#E0F2FE] transition-colors"
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
            </div>
          </div>
        )}
      </header>

      {/* Основной контент */}
      <main className="flex-1 max-w-5xl mx-auto px-4 sm:px-6 py-8 sm:py-12 w-full space-y-10 sm:space-y-12">
        {/* Заголовок */}
        <div className="space-y-2">
          <h1 className="text-3xl sm:text-4xl font-extrabold text-text-primary tracking-tight">
            Методика и ограничения
          </h1>
          <p className="text-text-secondary text-sm sm:text-base">
            Как устроен пайплайн HydroWatch Amur и где он ошибается
          </p>
        </div>

        {/* 1. ПАЙПЛАЙН */}
        <section className="space-y-4">
          <div className="text-[11px] font-bold text-text-muted tracking-wider uppercase">
            1. ПАЙПЛАЙН ОБРАБОТКИ
          </div>

          <div className="space-y-3">
            {pipelineSteps.map((step) => (
              <div
                key={step.num}
                className="bg-white border border-[#EAECF0] rounded-xl p-4 sm:p-5 shadow-2xs flex flex-col sm:flex-row sm:items-start gap-3 sm:gap-4"
              >
                <div className="font-mono text-xl sm:text-2xl font-black text-text-muted/40 shrink-0">
                  {step.num}
                </div>
                <div className="space-y-1">
                  <h3 className="font-bold text-sm sm:text-base text-text-primary">{step.title}</h3>
                  <p className="text-xs sm:text-sm text-text-secondary leading-relaxed">{step.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* 2. ИЗВЕСТНЫЕ ОГРАНИЧЕНИЯ */}
        <section className="space-y-4">
          <div className="text-[11px] font-bold text-text-muted tracking-wider uppercase">
            2. ИЗВЕСТНЫЕ ОГРАНИЧЕНИЯ
          </div>

          <div className="space-y-3">
            {limitations.map((lim, i) => (
              <div
                key={i}
                className="bg-amber-50/50 border border-amber-200/80 rounded-xl p-4 shadow-2xs flex items-start gap-3"
              >
                <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
                <p className="text-xs sm:text-sm text-amber-900 leading-relaxed">{lim.text}</p>
              </div>
            ))}
          </div>
        </section>

        {/* 3. ОФИЦИАЛЬНАЯ МЕТРИКА И КРИТЕРИИ (id="metric") */}
        <section id="metric" className="space-y-5 scroll-mt-20">
          <div className="text-[11px] font-bold text-text-muted tracking-wider uppercase">
            3. ОФИЦИАЛЬНАЯ МЕТРИКА ОЦЕНКИ И САБМИТ (ТЗ И КРИТЕРИИ)
          </div>

          <div className="bg-white border border-[#BAE6FD] rounded-xl p-5 sm:p-6 shadow-2xs space-y-4">
            <div>
              <h2 className="text-lg font-bold text-slate-900">
                Формула Score КосмоХакатона 2026
              </h2>
              <p className="text-xs sm:text-sm text-text-secondary mt-1">
                Интегральная оценка объединяет точность выделения площади нового затопления, двух дат водного зеркала и штраф за ложные тревоги на контрольной межени:
              </p>
            </div>

            {/* Блок формулы */}
            <div className="bg-[#F0F9FF] border border-[#7DD3FC] rounded-xl p-4 font-mono text-xs sm:text-sm text-[#0369A1] font-bold text-center leading-relaxed">
              Score = 0.45 · Q_flood + 0.25 · Q_water_peak + 0.15 · Q_water_pre + 0.15 · Spec_base
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs pt-2">
              <div className="bg-slate-50 border border-slate-200 rounded-lg p-3 space-y-2">
                <div className="font-bold text-slate-900 flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-[#0284C7]" />
                  <span>Сходимость по 8 парам паводков (q)</span>
                </div>
                <div className="font-mono bg-white p-2 rounded border border-slate-200 text-[11px]">
                  q = max(0, 1 - |X_sub - X_ref| / max(X_ref, порог))
                </div>
                <ul className="list-disc list-inside text-text-secondary space-y-1">
                  <li>Порог для зоны затопления: <strong>50 га</strong></li>
                  <li>Порог для водного зеркала («до» и пик): <strong>200 га</strong></li>
                  <li>Компоненты усредняются по всем 8 паводковым событиям</li>
                </ul>
              </div>

              <div className="bg-slate-50 border border-slate-200 rounded-lg p-3 space-y-2">
                <div className="font-bold text-slate-900 flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-emerald-600" />
                  <span>Специфичность по 3 парам межени (Spec_base)</span>
                </div>
                <div className="font-mono bg-white p-2 rounded border border-slate-200 text-[11px]">
                  Spec_base = mean(1 - min(1, excess_share / 0.005))
                </div>
                <ul className="list-disc list-inside text-text-secondary space-y-1">
                  <li>Контроль ложных срабатываний при спаде воды</li>
                  <li>Допуск на ложные тревоги: <strong>0.5% от площади AOI</strong></li>
                  <li>Любое превышение жестко штрафует общий результат</li>
                </ul>
              </div>
            </div>

            {/* Обязательные критерии сдачи из CRITERIA.md */}
            <div className="border-t border-slate-200 pt-3 space-y-2">
              <h3 className="text-xs font-bold text-slate-900">
                Обязательные технические правила валидности сабмита:
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-[11px]">
                <div className="p-2.5 rounded bg-slate-50 border border-slate-200">
                  <span className="font-semibold block text-slate-800">11 пар без пропусков</span>
                  <span className="text-text-secondary">Перечень пар совпадает с sample_submission.csv, без NaN.</span>
                </div>
                <div className="p-2.5 rounded bg-slate-50 border border-slate-200">
                  <span className="font-semibold block text-slate-800">Физические ограничения</span>
                  <span className="text-text-secondary">Площади неотрицательны, и flood_ha ≤ water_peak_ha.</span>
                </div>
                <div className="p-2.5 rounded bg-slate-50 border border-slate-200">
                  <span className="font-semibold block text-slate-800">Правило 2% растра</span>
                  <span className="text-text-secondary">Расхождение площади растровой маски и CSV ≤ 2.0%.</span>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* 4. ИСТОЧНИКИ ДАННЫХ */}
        <section className="space-y-4">
          <div className="text-[11px] font-bold text-text-muted tracking-wider uppercase">
            4. ИСТОЧНИКИ ДАННЫХ
          </div>

          <div className="border border-[#EAECF0] rounded-xl overflow-x-auto bg-white shadow-2xs">
            <table className="w-full text-xs text-left min-w-[360px]">
              <thead className="border-b border-[#EAECF0] bg-[#F8FAFC] text-text-muted">
                <tr>
                  <th className="py-3 px-4 sm:px-5 font-semibold">Набор данных</th>
                  <th className="py-3 px-4 sm:px-5 font-semibold">Источник</th>
                  <th className="py-3 px-4 sm:px-5 font-semibold">Лицензия</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#F1F5F9]">
                {dataSources.map((row) => (
                  <tr key={row.name} className="hover:bg-[#F8FAFC]">
                    <td className="py-3 px-4 sm:px-5 font-medium text-text-primary">{row.name}</td>
                    <td className="py-3 px-4 sm:px-5 text-text-secondary">{row.source}</td>
                    <td className="py-3 px-4 sm:px-5 text-text-secondary">{row.license}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* 5. ССЫЛКИ */}
        <section className="space-y-4">
          <div className="text-[11px] font-bold text-text-muted tracking-wider uppercase">
            5. ССЫЛКИ И РЕСУРСЫ
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
            <a
              href="https://github.com/p4ulbr4dl3y/cosmohack-hydro-2026"
              target="_blank"
              rel="noreferrer"
              className="bg-white border border-[#EAECF0] hover:border-[#CBD5E1] rounded-xl p-4 shadow-card flex items-center justify-between text-xs font-medium text-text-primary group transition-all"
            >
              <div className="flex items-center gap-2.5">
                <span className="text-text-muted group-hover:text-text-primary transition-colors">
                  <ExternalLink className="w-4 h-4" />
                </span>
                <span>GitHub-репозиторий</span>
              </div>
              <ArrowRight className="w-3.5 h-3.5 text-text-muted group-hover:text-text-primary group-hover:translate-x-0.5 transition-all" />
            </a>

            <Link
              to="/api-docs"
              className="bg-white border border-[#EAECF0] hover:border-[#CBD5E1] rounded-xl p-4 shadow-card flex items-center justify-between text-xs font-medium text-text-primary group transition-all"
            >
              <div className="flex items-center gap-2.5">
                <FileCode className="w-4 h-4 text-text-muted group-hover:text-text-primary transition-colors" />
                <span>OpenAPI-спецификация</span>
              </div>
              <ArrowRight className="w-3.5 h-3.5 text-text-muted group-hover:text-text-primary group-hover:translate-x-0.5 transition-all" />
            </Link>

            <div className="bg-white border border-[#EAECF0] hover:border-[#CBD5E1] rounded-xl p-4 shadow-card flex items-center justify-between text-xs font-medium text-text-primary group transition-all cursor-pointer">
              <div className="flex items-center gap-2.5">
                <Boxes className="w-4 h-4 text-text-muted group-hover:text-text-primary transition-colors" />
                <span>Docker-образ</span>
              </div>
              <ArrowRight className="w-3.5 h-3.5 text-text-muted group-hover:text-text-primary group-hover:translate-x-0.5 transition-all" />
            </div>

            <div className="bg-white border border-[#EAECF0] hover:border-[#CBD5E1] rounded-xl p-4 shadow-card flex items-center justify-between text-xs font-medium text-text-primary group transition-all cursor-pointer">
              <div className="flex items-center gap-2.5">
                <FileText className="w-4 h-4 text-text-muted group-hover:text-text-primary transition-colors" />
                <span>Презентация (PDF)</span>
              </div>
              <ArrowRight className="w-3.5 h-3.5 text-text-muted group-hover:text-text-primary group-hover:translate-x-0.5 transition-all" />
            </div>
          </div>
        </section>
      </main>

      {/* Подвал */}
      <footer className="border-t border-[#EAECF0] bg-white py-6 sm:py-8 px-4 sm:px-8 mt-12 text-xs text-text-muted">
        <div className="max-w-5xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <div>© HydroWatch Amur, 2026.</div>
          <div>Данные Copernicus © ESA</div>
        </div>
      </footer>
    </div>
  );
};
