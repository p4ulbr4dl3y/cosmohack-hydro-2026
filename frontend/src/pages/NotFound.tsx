import React from 'react';
import { Link } from 'react-router-dom';
import { Home } from 'lucide-react';

export const NotFound: React.FC = () => {
  return (
    <div className="min-h-screen bg-[#FAFBFC] flex items-center justify-center p-6 text-text-primary font-sans">
      <div className="max-w-md w-full bg-white border border-[#EAECF0] rounded-2xl p-8 shadow-card text-center space-y-6">
        <div className="w-14 h-14 rounded-2xl bg-sky-50 border border-sky-100 flex items-center justify-center mx-auto">
          <img src="/icons/logo.png" alt="HydroWatch" className="w-8 h-8 object-contain" />
        </div>

        <div className="space-y-2">
          <div className="font-mono text-4xl font-extrabold text-[#0EA5E9]">404</div>
          <h1 className="text-xl font-bold text-text-primary">Страница не найдена</h1>
          <p className="text-text-secondary text-xs leading-relaxed">
            Запрошенная страница не существует или была перемещена. Проверьте правильность адреса.
          </p>
        </div>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
          <Link
            to="/"
            className="w-full sm:w-auto px-4 py-2 border border-[#EAECF0] bg-white hover:bg-slate-50 text-text-primary text-xs font-medium rounded-xl transition-colors flex items-center justify-center gap-1.5"
          >
            <Home className="w-3.5 h-3.5" />
            <span>На главную</span>
          </Link>
          <Link
            to="/dashboard"
            className="w-full sm:w-auto px-4 py-2 bg-[#0EA5E9] hover:bg-[#0284C7] text-white text-xs font-semibold rounded-xl transition-colors flex items-center justify-center gap-1.5 shadow-xs"
          >
            <span>Открыть дашборд</span>
          </Link>
        </div>
      </div>
    </div>
  );
};
