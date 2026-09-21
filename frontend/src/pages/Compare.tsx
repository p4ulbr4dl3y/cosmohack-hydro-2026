import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, RotateCcw } from 'lucide-react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { useUiStore } from '../store/uiStore';
import { WATER_COLORS } from '../lib/colors';
import { Legend } from '../components/map/Legend';
import { apiClient } from '../api/client';
import type { ReportData } from '../types/domain';

export const Compare: React.FC = () => {
  const { pairId = 'flood_2019_07_amur__blagoveshchensk' } = useParams<{ pairId: string }>();
  const navigate = useNavigate();
  const { compareMode, setCompareMode } = useUiStore();

  const [sliderPos, setSliderPos] = useState<number>(50); // процент 0 - 100
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [report, setReport] = useState<ReportData | null>(null);

  const containerRef = useRef<HTMLDivElement>(null);
  const mapBeforeRef = useRef<HTMLDivElement>(null);
  const mapPeakRef = useRef<HTMLDivElement>(null);

  const leafletBefore = useRef<L.Map | null>(null);
  const leafletPeak = useRef<L.Map | null>(null);

  const tileBeforeRef = useRef<L.TileLayer | null>(null);
  const tilePeakRef = useRef<L.TileLayer | null>(null);

  const layerWaterPre1Ref = useRef<L.GeoJSON | null>(null);
  const layerWaterPre2Ref = useRef<L.GeoJSON | null>(null);
  const layerWaterPeakRef = useRef<L.GeoJSON | null>(null);
  const layerFloodRef = useRef<L.GeoJSON | null>(null);
  const layerHydro1Ref = useRef<L.GeoJSON | null>(null);
  const layerHydro2Ref = useRef<L.GeoJSON | null>(null);

  const [layersVisibility, setLayersVisibility] = useState({
    flood: true,
    water_peak: true,
    water_pre: true,
    hydro: true,
  });

  const toggleLayerVis = (key: keyof typeof layersVisibility) => {
    setLayersVisibility((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  useEffect(() => {
    apiClient.fetchReport(pairId).then(setReport).catch(console.error);
  }, [pairId]);

  // Клавиатурная навигация: Esc -> назад, ArrowLeft / ArrowRight -> сдвиг слайдера
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        navigate(`/dashboard/${pairId}`);
      } else if (e.key === 'ArrowLeft') {
        setSliderPos((pos) => Math.max(5, pos - 5));
      } else if (e.key === 'ArrowRight') {
        setSliderPos((pos) => Math.min(95, pos + 5));
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [navigate, pairId]);

  // Логика перетаскивания
  const handlePointerDown = useCallback(() => {
    setIsDragging(true);
  }, []);

  const handlePointerMove = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      if (!isDragging || !containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const newPos = (x / rect.width) * 100;
      setSliderPos(Math.max(2, Math.min(98, newPos)));
    },
    [isDragging]
  );

  const handlePointerUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  const handleReset = () => {
    setSliderPos(50);
  };

  // Инициализация двух карт Leaflet с синхронизацией
  useEffect(() => {
    if (!mapBeforeRef.current || !mapPeakRef.current) return;
    if (leafletBefore.current || leafletPeak.current) return;

    const defaultCenter: L.LatLngExpression = [50.2899, 127.5378];
    const defaultZoom = 11;

    const map1 = L.map(mapBeforeRef.current, {
      preferCanvas: true,
      center: defaultCenter,
      zoom: defaultZoom,
      zoomControl: false,
      attributionControl: false,
    });

    const map2 = L.map(mapPeakRef.current, {
      preferCanvas: true,
      center: defaultCenter,
      zoom: defaultZoom,
      zoomControl: false,
      attributionControl: false,
    });

    // Синхронизация обеих карт
    let isSyncing = false;
    map1.on('move', () => {
      if (isSyncing) return;
      isSyncing = true;
      map2.setView(map1.getCenter(), map1.getZoom(), { animate: false });
      isSyncing = false;
    });

    map2.on('move', () => {
      if (isSyncing) return;
      isSyncing = true;
      map1.setView(map2.getCenter(), map2.getZoom(), { animate: false });
      isSyncing = false;
    });

    leafletBefore.current = map1;
    leafletPeak.current = map2;

    return () => {
      map1.remove();
      map2.remove();
      leafletBefore.current = null;
      leafletPeak.current = null;
    };
  }, []);

  // Обновление подложек на обеих картах
  useEffect(() => {
    const map1 = leafletBefore.current;
    const map2 = leafletPeak.current;
    if (!map1 || !map2) return;

    if (tileBeforeRef.current) map1.removeLayer(tileBeforeRef.current);
    if (tilePeakRef.current) map2.removeLayer(tilePeakRef.current);

    let tileUrl = 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png';
    let subdomains = 'abcd';

    if (compareMode === 'sar') {
      tileUrl = 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png';
    } else if (compareMode === 'msi') {
      tileUrl = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}';
      subdomains = 'abc';
    } else if (compareMode === 'masks') {
      tileUrl = 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png';
    }

    tileBeforeRef.current = L.tileLayer(tileUrl, { maxZoom: 19, subdomains, crossOrigin: true }).addTo(map1);
    tilePeakRef.current = L.tileLayer(tileUrl, { maxZoom: 19, subdomains, crossOrigin: true }).addTo(map2);
  }, [compareMode]);

  // Загрузка реальных слоёв GeoJSON и подгонка границ
  useEffect(() => {
    const map1 = leafletBefore.current;
    const map2 = leafletPeak.current;
    if (!map1 || !map2 || !pairId) return;

    let isMounted = true;

    // Загрузка границ AOI для обеих карт
    apiClient.fetchAoi().then((aoiData) => {
      if (!isMounted || !aoiData) return;
      const aoiStyle = {
        color: '#0EA5E9',
        weight: 2,
        dashArray: '4, 4',
        fillColor: '#0EA5E9',
        fillOpacity: 0.03,
      };
      L.geoJSON(aoiData, { style: aoiStyle }).addTo(map1);
      L.geoJSON(aoiData, { style: aoiStyle }).addTo(map2);
    }).catch(console.error);

    // Загрузка постоянной гидрографии OSM для обеих карт
    apiClient.fetchVectorLayer('hydrography_osm').then((hydroGeo) => {
      if (!isMounted || !hydroGeo) return;
      const hydroStyle = {
        color: '#2563EB',
        weight: 1.5,
        fillColor: '#3B82F6',
        fillOpacity: 0.45,
      };
      layerHydro1Ref.current = L.geoJSON(hydroGeo, { style: hydroStyle }).addTo(map1);
      layerHydro2Ref.current = L.geoJSON(hydroGeo, { style: hydroStyle }).addTo(map2);
    }).catch(console.error);

    // Загрузка водной маски "до" на карту 1 и карту 2
    apiClient.fetchLayerGeoJson(pairId, 'water_pre').then((preGeo) => {
      if (!isMounted || !preGeo?.features?.length) return;
      layerWaterPre1Ref.current = L.geoJSON(preGeo, {
        style: {
          color: WATER_COLORS.water_pre.color,
          weight: 1.5,
          fillColor: WATER_COLORS.water_pre.fillColor,
          fillOpacity: 0.65,
        },
      }).addTo(map1);

      layerWaterPre2Ref.current = L.geoJSON(preGeo, {
        style: {
          color: WATER_COLORS.water_pre.color,
          weight: 1.5,
          fillColor: WATER_COLORS.water_pre.fillColor,
          fillOpacity: 0.45,
        },
      }).addTo(map2);
    }).catch(console.error);

    // Загрузка водной маски "пик" на карту 2
    apiClient.fetchLayerGeoJson(pairId, 'water_peak').then((peakGeo) => {
      if (!isMounted || !peakGeo?.features?.length) return;
      layerWaterPeakRef.current = L.geoJSON(peakGeo, {
        style: {
          color: WATER_COLORS.water_peak.color,
          weight: 1.5,
          fillColor: WATER_COLORS.water_peak.fillColor,
          fillOpacity: 0.55,
        },
      }).addTo(map2);
    }).catch(console.error);

    // Загрузка маски нового затопления "паводок" (оранжевая) на карту 2
    apiClient.fetchLayerGeoJson(pairId, 'flood').then((floodGeo) => {
      if (!isMounted || !floodGeo?.features?.length) return;
      const floodL = L.geoJSON(floodGeo, {
        style: {
          color: WATER_COLORS.flood.color,
          weight: 2,
          fillColor: WATER_COLORS.flood.fillColor,
          fillOpacity: 0.85,
        },
      }).addTo(map2);
      layerFloodRef.current = floodL;

      // Подгонка границ карты под зону затопления, если она доступна
      const b = floodL.getBounds();
      if (b.isValid()) {
        map1.fitBounds(b, { padding: [50, 50], maxZoom: 12 });
        map2.fitBounds(b, { padding: [50, 50], maxZoom: 12 });
      }
    }).catch(console.error);

    return () => {
      isMounted = false;
    };
  }, [pairId]);

  // Синхронизация переключателей слоёв
  useEffect(() => {
    const map1 = leafletBefore.current;
    const map2 = leafletPeak.current;
    if (!map1 || !map2) return;

    if (layerFloodRef.current) {
      if (layersVisibility.flood && !map2.hasLayer(layerFloodRef.current)) {
        map2.addLayer(layerFloodRef.current);
      } else if (!layersVisibility.flood && map2.hasLayer(layerFloodRef.current)) {
        map2.removeLayer(layerFloodRef.current);
      }
    }

    if (layerWaterPeakRef.current) {
      if (layersVisibility.water_peak && !map2.hasLayer(layerWaterPeakRef.current)) {
        map2.addLayer(layerWaterPeakRef.current);
      } else if (!layersVisibility.water_peak && map2.hasLayer(layerWaterPeakRef.current)) {
        map2.removeLayer(layerWaterPeakRef.current);
      }
    }

    if (layerWaterPre1Ref.current) {
      if (layersVisibility.water_pre && !map1.hasLayer(layerWaterPre1Ref.current)) {
        map1.addLayer(layerWaterPre1Ref.current);
      } else if (!layersVisibility.water_pre && map1.hasLayer(layerWaterPre1Ref.current)) {
        map1.removeLayer(layerWaterPre1Ref.current);
      }
    }

    if (layerWaterPre2Ref.current) {
      if (layersVisibility.water_pre && !map2.hasLayer(layerWaterPre2Ref.current)) {
        map2.addLayer(layerWaterPre2Ref.current);
      } else if (!layersVisibility.water_pre && map2.hasLayer(layerWaterPre2Ref.current)) {
        map2.removeLayer(layerWaterPre2Ref.current);
      }
    }

    if (layerHydro1Ref.current) {
      if (layersVisibility.hydro && !map1.hasLayer(layerHydro1Ref.current)) {
        map1.addLayer(layerHydro1Ref.current);
      } else if (!layersVisibility.hydro && map1.hasLayer(layerHydro1Ref.current)) {
        map1.removeLayer(layerHydro1Ref.current);
      }
    }

    if (layerHydro2Ref.current) {
      if (layersVisibility.hydro && !map2.hasLayer(layerHydro2Ref.current)) {
        map2.addLayer(layerHydro2Ref.current);
      } else if (!layersVisibility.hydro && map2.hasLayer(layerHydro2Ref.current)) {
        map2.removeLayer(layerHydro2Ref.current);
      }
    }
  }, [layersVisibility]);

  return (
    <div
      ref={containerRef}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      className="relative w-screen h-screen overflow-hidden select-none bg-[#0A192F] font-sans"
    >
      {/* Top Header Bar */}
      <header className="absolute top-0 left-0 right-0 z-30 h-14 bg-white/95 backdrop-blur-sm border-b border-[#EAECF0] px-3 sm:px-4 flex items-center justify-between shadow-xs">
        <div className="flex items-center gap-2 sm:gap-3">
          <button
            onClick={() => navigate(`/dashboard/${pairId}`)}
            className="inline-flex items-center gap-1.5 text-xs font-medium text-text-secondary hover:text-text-primary px-2.5 sm:px-3 py-1.5 rounded-lg border border-[#EAECF0] bg-white hover:bg-slate-50 transition-colors shadow-2xs"
            title="Назад к дашборду"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Назад к дашборду</span>
          </button>

          <div className="hidden md:flex items-center gap-2 text-xs font-mono">
            <span className="font-semibold text-text-primary truncate max-w-[200px]">{pairId}</span>
            <span className="text-text-muted">|</span>
            <span className="text-text-secondary font-sans">Сравнение до / пик</span>
          </div>
        </div>

        <div className="hidden xl:flex items-center gap-1.5 bg-[#F8FAFC] border border-[#EAECF0] px-2 py-1 rounded-lg text-xs">
          <span className="text-[11px] text-text-muted font-medium mr-0.5">Слои:</span>
          <button
            onClick={() => toggleLayerVis('flood')}
            className={`px-2 py-0.5 rounded text-[11px] font-semibold transition-all flex items-center gap-1 border cursor-pointer ${
              layersVisibility.flood
                ? 'bg-orange-50 border-orange-200 text-[#F97316]'
                : 'bg-white border-slate-200 text-slate-400'
            }`}
          >
            <span className="w-2 h-2 rounded-xs bg-[#F97316]" />
            Затопление
          </button>
          <button
            onClick={() => toggleLayerVis('water_peak')}
            className={`px-2 py-0.5 rounded text-[11px] font-semibold transition-all flex items-center gap-1 border cursor-pointer ${
              layersVisibility.water_peak
                ? 'bg-cyan-50 border-cyan-200 text-[#0891B2]'
                : 'bg-white border-slate-200 text-slate-400'
            }`}
          >
            <span className="w-2 h-2 rounded-xs bg-[#06B6D4]" />
            Зеркало (пик)
          </button>
          <button
            onClick={() => toggleLayerVis('water_pre')}
            className={`px-2 py-0.5 rounded text-[11px] font-semibold transition-all flex items-center gap-1 border cursor-pointer ${
              layersVisibility.water_pre
                ? 'bg-blue-50 border-blue-200 text-[#2563EB]'
                : 'bg-white border-slate-200 text-slate-400'
            }`}
          >
            <span className="w-2 h-2 rounded-xs bg-[#60A5FA]" />
            Вода до
          </button>
          <button
            onClick={() => toggleLayerVis('hydro')}
            className={`px-2 py-0.5 rounded text-[11px] font-semibold transition-all flex items-center gap-1 border cursor-pointer ${
              layersVisibility.hydro
                ? 'bg-indigo-50 border-indigo-200 text-indigo-700'
                : 'bg-white border-slate-200 text-slate-400'
            }`}
          >
            <span className="w-2 h-2 rounded-xs bg-[#3B82F6]" />
            Реки (OSM)
          </button>
        </div>

        <div className="flex items-center gap-1.5 sm:gap-2.5">
          {/* Mode switch buttons */}
          <div className="flex items-center bg-[#F1F5F9] p-0.5 sm:p-1 rounded-lg border border-[#EAECF0]">
            {(['sar', 'msi', 'masks'] as const).map((m) => (
              <button
                key={m}
                onClick={() => setCompareMode(m)}
                className={`px-2 sm:px-3 py-1 text-[11px] sm:text-xs font-semibold rounded-md transition-all uppercase ${
                  compareMode === m
                    ? 'bg-white text-[#0EA5E9] shadow-xs'
                    : 'text-text-secondary hover:text-text-primary'
                }`}
              >
                {m === 'sar' ? 'SAR' : m === 'msi' ? 'MSI' : 'Маски'}
              </button>
            ))}
          </div>

          <button
            onClick={handleReset}
            className="px-2 sm:px-3 py-1.5 border border-[#EAECF0] bg-white hover:bg-slate-50 text-text-secondary hover:text-text-primary text-xs font-medium rounded-lg transition-colors flex items-center gap-1 shadow-2xs"
            title="Сбросить слайдер на 50%"
          >
            <RotateCcw className="w-3 h-3" />
            <span className="hidden sm:inline">Сбросить</span>
          </button>
        </div>
      </header>

      {/* Map Layers Container */}
      <div className="absolute inset-0 pt-14 pb-20 overflow-hidden">
        {/* Under layer (Before Flood - Map 1) */}
        <div className="absolute inset-0 z-0">
          <div ref={mapBeforeRef} className="w-full h-full" />

          {/* Left Pill (Before Watermark) */}
          <div className="absolute top-4 left-4 z-[1000] bg-white/95 backdrop-blur-sm border border-[#EAECF0] rounded-lg px-3 py-1.5 shadow-floating text-xs font-mono font-semibold text-text-primary flex items-center gap-2 pointer-events-none">
            <span className="w-2.5 h-2.5 rounded-full bg-[#60A5FA]" />
            <span>ДО · {report?.date_pre_sar || '13.06.2019'}</span>
          </div>
        </div>

        {/* Over layer (Peak Flood - Map 2) clipped by slider */}
        <div
          className="absolute inset-0 z-10 overflow-hidden"
          style={{ clipPath: `inset(0 0 0 ${sliderPos}%)` }}
        >
          <div ref={mapPeakRef} className="w-full h-full" />

          {/* Right Pill (Peak Watermark) */}
          <div className="absolute top-4 right-4 z-[1000] bg-white/95 backdrop-blur-sm border border-[#EAECF0] rounded-lg px-3 py-1.5 shadow-floating text-xs font-mono font-semibold text-[#F97316] flex items-center gap-2 pointer-events-none">
            <span className="w-2.5 h-2.5 rounded-full bg-[#F97316]" />
            <span>ПИК · {report?.date_peak_sar || '25.07.2019'}</span>
          </div>
        </div>

        {/* Draggable Divider Line & Handle */}
        <div
          className="absolute top-0 bottom-0 w-1 bg-white cursor-ew-resize z-20 shadow-2xl"
          style={{ left: `${sliderPos}%` }}
          onPointerDown={handlePointerDown}
        >
          <div className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-9 h-9 rounded-full bg-white text-text-secondary border-2 border-[#0EA5E9] shadow-floating flex items-center justify-center font-bold text-xs cursor-ew-resize hover:scale-110 active:scale-95 transition-transform">
            {'<->'}
          </div>
        </div>

        {/* Floating Legend on bottom right */}
        <div className="absolute bottom-4 right-5 z-[1000]">
          <Legend aoiKm2={report?.aoi_km2 || 1245} />
        </div>
      </div>

      {/* Bottom Overlay Bar */}
      <footer className="absolute bottom-0 left-0 right-0 h-16 sm:h-20 bg-white/95 backdrop-blur-sm border-t border-[#EAECF0] px-3 sm:px-8 flex items-center justify-between z-30 shadow-floating">
        {/* Left: Before flood */}
        <div className="space-y-0.5 text-left">
          <div className="font-mono text-xs sm:text-sm font-bold text-text-primary">
            ДО · {report?.date_pre_sar?.slice(5) || '13.06'}
          </div>
          <div className="text-[10px] sm:text-xs text-text-muted">
            {report ? `${Math.round(report.water_pre_ha).toLocaleString('ru-RU')} га` : '—'}
          </div>
        </div>

        {/* Center: Flood Delta */}
        <div className="text-center space-y-0.5">
          <div className="font-mono text-lg sm:text-2xl md:text-3xl font-extrabold text-[#F97316] tracking-tight">
            {report ? `+${Math.round(report.flood_ha).toLocaleString('ru-RU')}` : '—'} га
          </div>
          <div className="text-[10px] sm:text-xs text-text-secondary font-medium">
            новое затопление
          </div>
        </div>

        {/* Right: Peak flood */}
        <div className="text-right space-y-0.5">
          <div className="font-mono text-xs sm:text-sm font-bold text-text-primary">
            ПИК · {report?.date_peak_sar?.slice(5) || '25.07'}
          </div>
          <div className="text-[10px] sm:text-xs text-text-muted">
            {report ? `${Math.round(report.water_peak_ha).toLocaleString('ru-RU')} га` : '—'}
          </div>
        </div>
      </footer>
    </div>
  );
};
