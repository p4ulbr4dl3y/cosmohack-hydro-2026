import React, { useState } from 'react';
import { ChevronDown, ChevronUp, Layers } from 'lucide-react';
import { useUiStore } from '../../store/uiStore';
import { WATER_COLORS } from '../../lib/colors';
import type { BasemapType, GradientOverlayMode } from '../../types/domain';

export const LayerControl: React.FC = () => {
  const [isOpen, setIsOpen] = useState(true);
  const {
    layers,
    toggleLayer,
    setLayerOpacity,
    basemap,
    setBasemap,
    showLegend,
    toggleLegend,
    gradientMode,
    setGradientMode,
    gradientOpacity,
    setGradientOpacity,
  } = useUiStore();

  const handleBasemapChange = (type: BasemapType) => {
    setBasemap(type);
  };

  return (
    <div className="bg-white/95 backdrop-blur-sm border border-[#EAECF0] rounded-xl shadow-floating w-44 text-xs select-none overflow-hidden">
      {/* Заголовок */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-2.5 py-1.5 flex items-center justify-between border-b border-[#F1F5F9] hover:bg-[#F8FAFC] transition-colors cursor-pointer"
      >
        <div className="flex items-center gap-1.5 font-bold text-[10px] text-text-muted tracking-wider uppercase">
          <Layers className="w-3.5 h-3.5" />
          <span>СЛОИ</span>
        </div>
        {isOpen ? (
          <ChevronUp className="w-3.5 h-3.5 text-text-muted" />
        ) : (
          <ChevronDown className="w-3.5 h-3.5 text-text-muted" />
        )}
      </button>

      {isOpen && (
        <div className="p-2 space-y-2.5 max-h-[min(280px,calc(100vh-340px))] overflow-y-auto">
          {/* Раздел: Маски */}
          <div>
            <div className="text-[10px] font-bold text-text-muted uppercase tracking-wider mb-1.5">
              Маски затопления
            </div>
            <div className="space-y-1.5">
              {/* Затопление */}
              <label className="flex items-center justify-between cursor-pointer py-0.5 group">
                <div className="flex items-center gap-1.5">
                  <span
                    className="w-2.5 h-2.5 rounded-full shrink-0"
                    style={{ backgroundColor: WATER_COLORS.flood.fillColor }}
                  />
                  <span className="text-text-primary text-[11px] group-hover:text-text-secondary">
                    Новое затопление
                  </span>
                </div>
                <input
                  type="checkbox"
                  checked={layers.flood}
                  onChange={() => toggleLayer('flood')}
                  className="w-3.5 h-3.5 accent-[#0EA5E9] rounded cursor-pointer"
                />
              </label>

              {/* Вода на пик */}
              <label className="flex items-center justify-between cursor-pointer py-0.5 group">
                <div className="flex items-center gap-1.5">
                  <span
                    className="w-2.5 h-2.5 rounded-full shrink-0"
                    style={{ backgroundColor: WATER_COLORS.water_peak.fillColor }}
                  />
                  <span className="text-text-primary text-[11px] group-hover:text-text-secondary">
                    Вода на пик
                  </span>
                </div>
                <input
                  type="checkbox"
                  checked={layers.water_peak}
                  onChange={() => toggleLayer('water_peak')}
                  className="w-3.5 h-3.5 accent-[#0EA5E9] rounded cursor-pointer"
                />
              </label>

              {/* Вода на до */}
              <label className="flex items-center justify-between cursor-pointer py-0.5 group">
                <div className="flex items-center gap-1.5">
                  <span
                    className="w-2.5 h-2.5 rounded-full shrink-0"
                    style={{ backgroundColor: WATER_COLORS.water_pre.fillColor }}
                  />
                  <span className="text-text-primary text-[11px] group-hover:text-text-secondary">
                    Вода на до
                  </span>
                </div>
                <input
                  type="checkbox"
                  checked={layers.water_pre}
                  onChange={() => toggleLayer('water_pre')}
                  className="w-3.5 h-3.5 accent-[#0EA5E9] rounded cursor-pointer"
                />
              </label>

              {/* Постоянная вода */}
              <label className="flex items-center justify-between cursor-pointer py-0.5 group">
                <div className="flex items-center gap-1.5">
                  <span
                    className="w-2.5 h-2.5 rounded-full shrink-0"
                    style={{ backgroundColor: WATER_COLORS.permanent.fillColor }}
                  />
                  <span className="text-text-primary text-[11px] group-hover:text-text-secondary">
                    Постоянная вода
                  </span>
                </div>
                <input
                  type="checkbox"
                  checked={layers.permanent}
                  onChange={() => toggleLayer('permanent')}
                  className="w-3.5 h-3.5 accent-[#0EA5E9] rounded cursor-pointer"
                />
              </label>

              {/* Убыль воды */}
              <label className="flex items-center justify-between cursor-pointer py-0.5 group">
                <div className="flex items-center gap-1.5">
                  <span
                    className="w-2.5 h-2.5 rounded-full shrink-0 border border-dashed"
                    style={{
                      backgroundColor: 'rgba(167, 139, 250, 0.25)',
                      borderColor: WATER_COLORS.receded.color,
                    }}
                  />
                  <span className="text-text-primary text-[11px] group-hover:text-text-secondary">
                    Убыль воды
                  </span>
                </div>
                <input
                  type="checkbox"
                  checked={layers.receded}
                  onChange={() => toggleLayer('receded')}
                  className="w-3.5 h-3.5 accent-[#0EA5E9] rounded cursor-pointer"
                />
              </label>
            </div>
          </div>

          {/* Раздел: Подложки */}
          <div className="pt-2 border-t border-[#F1F5F9]">
            <div className="text-[10px] font-bold text-text-muted uppercase tracking-wider mb-1.5">
              Подложка (сцена Sentinel)
            </div>
            <div className="space-y-1">
              {[
                { id: 'sar_vv', label: 'SAR VV (пик)' },
                { id: 'sar_vh', label: 'SAR VH (пик)' },
                { id: 'msi_true', label: 'MSI True Color' },
                { id: 'msi_false', label: 'MSI False Color' },
              ].map((item) => (
                <label
                  key={item.id}
                  className="flex items-center gap-2 cursor-pointer py-0.5 group"
                >
                  <input
                    type="radio"
                    name="basemap"
                    value={item.id}
                    checked={basemap === item.id}
                    onChange={() => handleBasemapChange(item.id as BasemapType)}
                    className="w-3.5 h-3.5 accent-[#0EA5E9] cursor-pointer"
                  />
                  <span className="text-text-primary text-[11px] group-hover:text-text-secondary">
                    {item.label}
                  </span>
                </label>
              ))}
            </div>
          </div>

          {/* Раздел: Векторы */}
          <div className="pt-2 border-t border-[#F1F5F9]">
            <div className="text-[10px] font-bold text-text-muted uppercase tracking-wider mb-1.5">
              Векторы
            </div>
            <div className="space-y-1.5">
              <label className="flex items-center justify-between cursor-pointer py-0.5 group">
                <span className="text-text-primary text-[11px] group-hover:text-text-secondary">
                  Граница AOI
                </span>
                <input
                  type="checkbox"
                  checked={layers.aoi_boundary}
                  onChange={() => toggleLayer('aoi_boundary')}
                  className="w-3.5 h-3.5 accent-[#0EA5E9] rounded cursor-pointer"
                />
              </label>

              <label className="flex items-center justify-between cursor-pointer py-0.5 group">
                <span className="text-text-primary text-[11px] group-hover:text-text-secondary">
                  Сеть OSM
                </span>
                <input
                  type="checkbox"
                  checked={layers.osm_hydro}
                  onChange={() => toggleLayer('osm_hydro')}
                  className="w-3.5 h-3.5 accent-[#0EA5E9] rounded cursor-pointer"
                />
              </label>

              <label className="flex items-center justify-between cursor-pointer py-0.5 group">
                <span className="text-text-primary text-[11px] group-hover:text-text-secondary">
                  HydroSHEDS
                </span>
                <input
                  type="checkbox"
                  checked={layers.hydrosheds}
                  onChange={() => toggleLayer('hydrosheds')}
                  className="w-3.5 h-3.5 accent-[#0EA5E9] rounded cursor-pointer"
                />
              </label>

              <label className="flex items-center justify-between cursor-pointer py-0.5 group">
                <span className="text-text-primary text-[11px] group-hover:text-text-secondary">
                  Легенда карты
                </span>
                <input
                  type="checkbox"
                  checked={showLegend}
                  onChange={toggleLegend}
                  className="w-3.5 h-3.5 accent-[#0EA5E9] rounded cursor-pointer"
                />
              </label>
            </div>
          </div>

          {/* Раздел: Растровый градиент */}
          <div className="pt-2 border-t border-[#F1F5F9]">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-[10px] font-bold text-text-muted uppercase tracking-wider">
                Растровый градиент
              </span>
              <span className="font-mono text-[10px] text-text-secondary">
                {gradientMode !== 'none' ? `${Math.round(gradientOpacity * 100)}%` : 'Выкл'}
              </span>
            </div>

            <div className="space-y-1">
              {[
                { id: 'flood', label: 'Затопление (Градиент)' },
                { id: 'water_peak', label: 'Пик половодья' },
                { id: 'water_pre', label: 'Базовое русло' },
                { id: 'none', label: 'Отключить' },
              ].map((item) => (
                <label key={item.id} className="flex items-center gap-1.5 cursor-pointer py-0.5 group">
                  <input
                    type="radio"
                    name="gradientMode"
                    checked={gradientMode === item.id}
                    onChange={() => setGradientMode(item.id as GradientOverlayMode)}
                    className="w-3.5 h-3.5 accent-[#0EA5E9] cursor-pointer"
                  />
                  <span className="text-text-primary text-[11px] group-hover:text-text-secondary">
                    {item.label}
                  </span>
                </label>
              ))}
            </div>

            {gradientMode !== 'none' && (
              <div className="mt-2 pt-1.5 border-t border-slate-100">
                <div className="flex items-center justify-between mb-1 text-[10px] text-text-muted">
                  <span>Прозрачность растра</span>
                  <span className="font-mono text-text-primary font-medium">
                    {Math.round(gradientOpacity * 100)}%
                  </span>
                </div>
                <input
                  type="range"
                  min="10"
                  max="100"
                  step="5"
                  value={Math.round(gradientOpacity * 100)}
                  onChange={(e) => setGradientOpacity(Number(e.target.value) / 100)}
                  className="w-full h-1 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-[#0EA5E9]"
                />
              </div>
            )}
          </div>

          {/* Раздел: Прозрачность векторов */}
          <div className="pt-2 border-t border-[#F1F5F9]">
            <div className="flex items-center justify-between mb-1">
              <span className="text-[10px] font-bold text-text-muted uppercase tracking-wider">
                Векторы (прозрачность)
              </span>
              <span className="font-mono text-[11px] text-text-primary font-medium">
                {Math.round(layers.opacity * 100)}%
              </span>
            </div>
            <input
              type="range"
              min="0"
              max="100"
              value={Math.round(layers.opacity * 100)}
              onChange={(e) => setLayerOpacity(Number(e.target.value) / 100)}
              className="w-full h-1 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-[#0EA5E9]"
            />
          </div>
        </div>
      )}
    </div>
  );
};
