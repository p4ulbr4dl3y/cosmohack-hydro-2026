import React, { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { ChevronUp, ChevronDown, Droplets } from 'lucide-react';
import { useUiStore } from '../../store/uiStore';
import { apiClient } from '../../api/client';
import { WATER_COLORS } from '../../lib/colors';
import { LayerControl } from './LayerControl';
import { Legend } from './Legend';
import type { Pair } from '../../types/domain';

interface MapContainerProps {
  currentPair?: Pair | null;
  interactive?: boolean;
  showControls?: boolean;
  className?: string;
}

export const geojsonCache = new Map<string, any>();

const GRADIENT_CONFIGS: Record<
  string,
  {
    title: string;
    subtitle: string;
    min: string;
    mid: string;
    max: string;
    gradient: string;
  }
> = {
  flood: {
    title: 'Интенсивность затопления (SAR / Otsu)',
    subtitle: 'Глубина зеркала воды',
    min: '0.1 м (кромка)',
    mid: '1.5 м',
    max: '4.0+ м (стрежень)',
    gradient: 'linear-gradient(to right, #fed7aa, #fb923c, #ef4444, #991b1b)',
  },
  water_peak: {
    title: 'Зеркало воды на пик половодья',
    subtitle: 'Sentinel-1 SAR пиковый паводок',
    min: 'Мелководье',
    mid: 'Средняя глубина',
    max: 'Глубоководье',
    gradient: 'linear-gradient(to right, #bae6fd, #38bdf8, #0ea5e9, #0284c7, #1e3a8a)',
  },
  water_pre: {
    title: 'Базовый гидрологический створ',
    subtitle: 'Меженное русло реки',
    min: 'Берег',
    mid: 'Русло',
    max: 'Фарватер',
    gradient: 'linear-gradient(to right, #cffafe, #38bdf8, #2563eb, #1e3a8a)',
  },
};

export const MapContainer: React.FC<MapContainerProps> = ({
  currentPair,
  interactive = true,
  showControls = true,
  className = '',
}) => {
  const mapRef = useRef<HTMLDivElement>(null);
  const leafletMap = useRef<L.Map | null>(null);
  const canvasRendererRef = useRef<L.Canvas | null>(null);
  const tileLayerRef = useRef<L.TileLayer | null>(null);

  // Группы слоёв
  const aoiLayerGroup = useRef<L.GeoJSON | null>(null);
  const floodLayerGroup = useRef<L.GeoJSON | null>(null);
  const waterPeakLayerGroup = useRef<L.GeoJSON | null>(null);
  const waterPreLayerGroup = useRef<L.GeoJSON | null>(null);
  const osmHydroLayerGroup = useRef<L.GeoJSON | null>(null);
  const hydroshedsLayerGroup = useRef<L.GeoJSON | null>(null);
  const gradientOverlayRef = useRef<L.ImageOverlay | null>(null);
  const lastFittedPairIdRef = useRef<string | null>(null);

  const [mouseCoords, setMouseCoords] = useState<{ lat: number; lng: number }>({
    lat: 50.2899,
    lng: 127.5378,
  });
  const [zoomLevel, setZoomLevel] = useState<number>(10);
  const [aoiFeatures, setAoiFeatures] = useState<any>(null);
  const [showGradientBar, setShowGradientBar] = useState<boolean>(true);

  const {
    layers,
    basemap,
    activePairId,
    gradientMode,
    gradientOpacity,
    setGradientOpacity,
  } = useUiStore();
  const effectivePairId = currentPair?.pair_id || activePairId;
  const activeGradientConfig = gradientMode !== 'none' ? GRADIENT_CONFIGS[gradientMode] : null;

  // Инициализация карты Leaflet
  useEffect(() => {
    if (!mapRef.current || leafletMap.current) return;

    const canvasRenderer = L.canvas({ padding: 0.5 });
    canvasRendererRef.current = canvasRenderer;

    const map = L.map(mapRef.current, {
      preferCanvas: true,
      renderer: canvasRenderer,
      center: [50.2899, 127.5378],
      zoom: 10,
      zoomControl: false,
      attributionControl: false,
      dragging: interactive,
      touchZoom: interactive,
      doubleClickZoom: interactive,
      scrollWheelZoom: interactive,
      boxZoom: interactive,
      keyboard: interactive,
    });

    if (interactive) {
      L.control.zoom({ position: 'topleft' }).addTo(map);

      map.on('mousemove', (e) => {
        setMouseCoords({
          lat: e.latlng.lat,
          lng: e.latlng.lng,
        });
      });

      map.on('zoomend', () => {
        setZoomLevel(map.getZoom());
      });
    }

    leafletMap.current = map;

    return () => {
      map.remove();
      leafletMap.current = null;
      canvasRendererRef.current = null;
    };
  }, [interactive]);

  // Обновление тайлов подложки
  useEffect(() => {
    const map = leafletMap.current;
    if (!map) return;

    if (tileLayerRef.current) {
      map.removeLayer(tileLayerRef.current);
    }

    let tileUrl = 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png';
    let subdomains = 'abcd';

    if (basemap === 'sar_vv') {
      tileUrl = 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png';
    } else if (basemap === 'sar_vh') {
      tileUrl = 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png';
    } else if (basemap === 'msi_true') {
      tileUrl = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}';
      subdomains = 'abc';
    } else if (basemap === 'msi_false') {
      tileUrl = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}';
    }

    const newTile = L.tileLayer(tileUrl, {
      maxZoom: 19,
      subdomains: subdomains,
      crossOrigin: true,
    }).addTo(map);

    tileLayerRef.current = newTile;
  }, [basemap]);

  // Однократная загрузка полигонов AOI (с кэшированием)
  useEffect(() => {
    let isMounted = true;
    const cachedAoi = geojsonCache.get('aoi');
    if (cachedAoi) {
      setAoiFeatures(cachedAoi);
      return;
    }

    apiClient.fetchAoi().then((data) => {
      if (isMounted && data) {
        geojsonCache.set('aoi', data);
        setAoiFeatures(data);
      }
    }).catch(console.error);

    return () => {
      isMounted = false;
    };
  }, []);

  // Отрисовка векторного слоя AOI и подгонка границ при смене пары или AOI
  useEffect(() => {
    const map = leafletMap.current;
    if (!map || !aoiFeatures) return;

    if (aoiLayerGroup.current) {
      map.removeLayer(aoiLayerGroup.current);
      aoiLayerGroup.current = null;
    }

    if (!layers.aoi_boundary) return;

    const layer = L.geoJSON(aoiFeatures, {
      renderer: canvasRendererRef.current || L.canvas({ padding: 0.5 }),
      style: (feature: any) => {
        const isCurrent =
          currentPair?.aoi_id &&
          feature?.properties?.aoi_id === currentPair.aoi_id;
        return {
          color: isCurrent ? '#0EA5E9' : '#64748B',
          weight: isCurrent ? 2.5 : 1.5,
          dashArray: isCurrent ? undefined : '5, 5',
          fillColor: isCurrent ? '#0EA5E9' : '#94A3B8',
          fillOpacity: isCurrent ? 0.05 : 0.02,
        };
      },
    } as any).addTo(map);

    aoiLayerGroup.current = layer;

    // Подгонка границ только при фактической смене пары, чтобы избежать дрожания
    const currentPairId = currentPair?.pair_id;
    if (currentPairId && lastFittedPairIdRef.current !== currentPairId) {
      lastFittedPairIdRef.current = currentPairId;
      if (currentPair?.aoi_id) {
        const matchFeat = aoiFeatures.features?.find(
          (f: any) => f.properties?.aoi_id === currentPair.aoi_id
        );
        if (matchFeat) {
          const tempLayer = L.geoJSON(matchFeat, {
            renderer: canvasRendererRef.current || L.canvas({ padding: 0.5 }),
          } as any);
          const b = tempLayer.getBounds();
          if (b.isValid()) {
            map.fitBounds(b, { padding: [40, 40], maxZoom: 12, animate: false });
          }
        } else if (currentPair.bounds_4326) {
          const [minX, minY, maxX, maxY] = currentPair.bounds_4326;
          map.fitBounds(
            [
              [minY, minX],
              [maxY, maxX],
            ],
            { padding: [40, 40], maxZoom: 12, animate: false }
          );
        }
      }
    }
  }, [aoiFeatures, currentPair?.pair_id, layers.aoi_boundary]);

  // Загрузка и отрисовка гидрографии OSM
  useEffect(() => {
    const map = leafletMap.current;
    if (!map) return;

    if (!layers.osm_hydro) {
      if (osmHydroLayerGroup.current && map.hasLayer(osmHydroLayerGroup.current)) {
        map.removeLayer(osmHydroLayerGroup.current);
      }
      return;
    }

    if (osmHydroLayerGroup.current) {
      if (!map.hasLayer(osmHydroLayerGroup.current)) {
        map.addLayer(osmHydroLayerGroup.current);
      }
      return;
    }

    const cachedOsm = geojsonCache.get('hydrography_osm');
    if (cachedOsm) {
      const layer = L.geoJSON(cachedOsm, {
        renderer: canvasRendererRef.current || L.canvas({ padding: 0.5 }),
        style: {
          color: '#3B82F6',
          weight: 1.5,
          opacity: 0.7,
          fillColor: '#60A5FA',
          fillOpacity: 0.3,
        },
      } as any).addTo(map);
      osmHydroLayerGroup.current = layer;
      return;
    }

    apiClient.fetchVectorLayer('hydrography_osm').then((geo) => {
      if (geo && leafletMap.current) {
        geojsonCache.set('hydrography_osm', geo);
        const layer = L.geoJSON(geo, {
          renderer: canvasRendererRef.current || L.canvas({ padding: 0.5 }),
          style: {
            color: '#3B82F6',
            weight: 1.5,
            opacity: 0.7,
            fillColor: '#60A5FA',
            fillOpacity: 0.3,
          },
        } as any).addTo(leafletMap.current);
        osmHydroLayerGroup.current = layer;
      }
    }).catch(() => {});
  }, [layers.osm_hydro]);

  // Загрузка и отрисовка бассейнов HydroSHEDS
  useEffect(() => {
    const map = leafletMap.current;
    if (!map) return;

    if (!layers.hydrosheds) {
      if (hydroshedsLayerGroup.current && map.hasLayer(hydroshedsLayerGroup.current)) {
        map.removeLayer(hydroshedsLayerGroup.current);
      }
      return;
    }

    if (hydroshedsLayerGroup.current) {
      if (!map.hasLayer(hydroshedsLayerGroup.current)) {
        map.addLayer(hydroshedsLayerGroup.current);
      }
      return;
    }

    const cachedBasins = geojsonCache.get('basins_hydrosheds');
    if (cachedBasins) {
      const layer = L.geoJSON(cachedBasins, {
        renderer: canvasRendererRef.current || L.canvas({ padding: 0.5 }),
        style: {
          color: '#8B5CF6',
          weight: 1.5,
          dashArray: '3, 4',
          opacity: 0.6,
          fillColor: '#C4B5FD',
          fillOpacity: 0.08,
        },
      } as any).addTo(map);
      hydroshedsLayerGroup.current = layer;
      return;
    }

    apiClient.fetchVectorLayer('basins_hydrosheds').then((geo) => {
      if (geo && leafletMap.current) {
        geojsonCache.set('basins_hydrosheds', geo);
        const layer = L.geoJSON(geo, {
          renderer: canvasRendererRef.current || L.canvas({ padding: 0.5 }),
          style: {
            color: '#8B5CF6',
            weight: 1.5,
            dashArray: '3, 4',
            opacity: 0.6,
            fillColor: '#C4B5FD',
            fillOpacity: 0.08,
          },
        } as any).addTo(leafletMap.current);
        hydroshedsLayerGroup.current = layer;
      }
    }).catch(() => {});
  }, [layers.hydrosheds]);

  // Загрузка слоёв масок затопления и воды для pairId (ТОЛЬКО при смене pairId)
  useEffect(() => {
    const map = leafletMap.current;
    if (!map || !effectivePairId) return;

    // Очистка предыдущих слоёв масок
    if (floodLayerGroup.current) {
      map.removeLayer(floodLayerGroup.current);
      floodLayerGroup.current = null;
    }
    if (waterPeakLayerGroup.current) {
      map.removeLayer(waterPeakLayerGroup.current);
      waterPeakLayerGroup.current = null;
    }
    if (waterPreLayerGroup.current) {
      map.removeLayer(waterPreLayerGroup.current);
      waterPreLayerGroup.current = null;
    }

    let isMounted = true;

    const loadMask = async (layerName: 'flood' | 'water_peak' | 'water_pre') => {
      const cacheKey = `${effectivePairId}_${layerName}`;
      let geojson = geojsonCache.get(cacheKey);

      if (!geojson) {
        try {
          geojson = await apiClient.fetchLayerGeoJson(effectivePairId, layerName);
          if (geojson) {
            geojsonCache.set(cacheKey, geojson);
          }
        } catch (err) {
          console.error(`Error loading layer ${layerName}`, err);
          return;
        }
      }

      if (!isMounted || !leafletMap.current || !geojson?.features?.length) return;

      const colorCfg = WATER_COLORS[layerName];
      const targetFill = (colorCfg.fillOpacity || 0.5) * layers.opacity;
      const targetStroke = (colorCfg.opacity || 0.8) * layers.opacity;

      const gjLayer = L.geoJSON(geojson, {
        renderer: canvasRendererRef.current || L.canvas({ padding: 0.5 }),
        style: {
          color: colorCfg.color,
          weight: (colorCfg as any).weight || 1,
          fillColor: colorCfg.fillColor,
          fillOpacity: 0,
          opacity: 0,
        },
      } as any);

      if (layerName === 'flood') {
        floodLayerGroup.current = gjLayer;
        if (layers.flood) gjLayer.addTo(leafletMap.current);
      } else if (layerName === 'water_peak') {
        waterPeakLayerGroup.current = gjLayer;
        if (layers.water_peak) gjLayer.addTo(leafletMap.current);
      } else if (layerName === 'water_pre') {
        waterPreLayerGroup.current = gjLayer;
        if (layers.water_pre) gjLayer.addTo(leafletMap.current);
      }

      // Плавное анимированное появление для бесшовного визуального восприятия
      const start = performance.now();
      const duration = 250;
      const animateFade = (now: number) => {
        if (!isMounted) return;
        const p = Math.min(1, (now - start) / duration);
        const ease = 1 - Math.pow(1 - p, 3);
        gjLayer.setStyle({
          fillOpacity: targetFill * ease,
          opacity: targetStroke * ease,
        });
        if (p < 1) requestAnimationFrame(animateFade);
      };
      requestAnimationFrame(animateFade);
    };

    loadMask('flood');
    loadMask('water_peak');
    loadMask('water_pre');

    return () => {
      isMounted = false;
    };
  }, [effectivePairId]);

  // Быстрое обновление стиля прозрачности без повторной загрузки или пересборки слоёв
  useEffect(() => {
    const opacity = layers.opacity;

    if (floodLayerGroup.current) {
      floodLayerGroup.current.setStyle({
        fillOpacity: (WATER_COLORS.flood.fillOpacity || 0.5) * opacity,
        opacity: (WATER_COLORS.flood.opacity || 0.8) * opacity,
      });
    }

    if (waterPeakLayerGroup.current) {
      waterPeakLayerGroup.current.setStyle({
        fillOpacity: (WATER_COLORS.water_peak.fillOpacity || 0.5) * opacity,
        opacity: (WATER_COLORS.water_peak.opacity || 0.8) * opacity,
      });
    }

    if (waterPreLayerGroup.current) {
      waterPreLayerGroup.current.setStyle({
        fillOpacity: (WATER_COLORS.water_pre.fillOpacity || 0.5) * opacity,
        opacity: (WATER_COLORS.water_pre.opacity || 0.8) * opacity,
      });
    }
  }, [layers.opacity]);

  // Быстрое переключение слоя затопления
  useEffect(() => {
    const map = leafletMap.current;
    if (!map || !floodLayerGroup.current) return;
    if (layers.flood && !map.hasLayer(floodLayerGroup.current)) {
      map.addLayer(floodLayerGroup.current);
    } else if (!layers.flood && map.hasLayer(floodLayerGroup.current)) {
      map.removeLayer(floodLayerGroup.current);
    }
  }, [layers.flood]);

  // Быстрое переключение слоя water_peak
  useEffect(() => {
    const map = leafletMap.current;
    if (!map || !waterPeakLayerGroup.current) return;
    if (layers.water_peak && !map.hasLayer(waterPeakLayerGroup.current)) {
      map.addLayer(waterPeakLayerGroup.current);
    } else if (!layers.water_peak && map.hasLayer(waterPeakLayerGroup.current)) {
      map.removeLayer(waterPeakLayerGroup.current);
    }
  }, [layers.water_peak]);

  // Быстрое переключение слоя water_pre
  useEffect(() => {
    const map = leafletMap.current;
    if (!map || !waterPreLayerGroup.current) return;
    if (layers.water_pre && !map.hasLayer(waterPreLayerGroup.current)) {
      map.addLayer(waterPreLayerGroup.current);
    } else if (!layers.water_pre && map.hasLayer(waterPreLayerGroup.current)) {
      map.removeLayer(waterPreLayerGroup.current);
    }
  }, [layers.water_pre]);

  // Непрерывный растровый градиентный оверлей (L.imageOverlay)
  useEffect(() => {
    const map = leafletMap.current;
    if (!map) return;

    if (gradientOverlayRef.current) {
      map.removeLayer(gradientOverlayRef.current);
      gradientOverlayRef.current = null;
    }

    if (gradientMode === 'none' || !effectivePairId) return;

    let isMounted = true;

    const setupOverlay = async () => {
      try {
        const meta = await apiClient.fetchOverlayMeta(effectivePairId, gradientMode);
        if (!isMounted || !leafletMap.current) return;

        let imageBounds: L.LatLngBoundsExpression;
        if (meta?.bounds && Array.isArray(meta.bounds) && meta.bounds.length === 2) {
          imageBounds = meta.bounds;
        } else if (currentPair?.bounds_4326) {
          const [minX, minY, maxX, maxY] = currentPair.bounds_4326;
          imageBounds = [
            [minY, minX],
            [maxY, maxX],
          ];
        } else {
          imageBounds = [
            [50.0, 127.0],
            [51.0, 128.0],
          ];
        }

        const overlayUrl = apiClient.getOverlayUrl(effectivePairId, gradientMode, true);
        const overlay = L.imageOverlay(overlayUrl, imageBounds, {
          opacity: 0,
          interactive: false,
        }).addTo(leafletMap.current);

        gradientOverlayRef.current = overlay;

        // Плавное анимированное появление оверлея
        const targetOpacity = gradientOpacity;
        const start = performance.now();
        const duration = 250;
        const animateFade = (now: number) => {
          if (!isMounted || !gradientOverlayRef.current) return;
          const p = Math.min(1, (now - start) / duration);
          const ease = 1 - Math.pow(1 - p, 3);
          overlay.setOpacity(targetOpacity * ease);
          if (p < 1) requestAnimationFrame(animateFade);
        };
        requestAnimationFrame(animateFade);
      } catch (err) {
        console.error('Failed to load raster gradient overlay', err);
      }
    };

    setupOverlay();

    return () => {
      isMounted = false;
      if (gradientOverlayRef.current && leafletMap.current) {
        leafletMap.current.removeLayer(gradientOverlayRef.current);
        gradientOverlayRef.current = null;
      }
    };
  }, [effectivePairId, gradientMode, currentPair]);

  // Быстрое обновление прозрачности градиентного оверлея
  useEffect(() => {
    if (gradientOverlayRef.current) {
      gradientOverlayRef.current.setOpacity(gradientOpacity);
    }
  }, [gradientOpacity]);

  return (
    <div className={`relative w-full h-full overflow-hidden ${className}`}>
      {/* Корень карты */}
      <div ref={mapRef} className="w-full h-full z-0" />

      {/* Плавающий LayerControl (верхний правый угол) */}
      {showControls && (
        <div className="absolute top-4 right-4 z-[1000]">
          <LayerControl />
        </div>
      )}

      {/* Плавающая легенда (нижний правый угол) */}
      {showControls && (
        <div className="absolute bottom-4 right-4 z-[1000]">
          <Legend aoiKm2={currentPair?.aoi_km2 || 1245} />
        </div>
      )}

      {/* Плавающая плашка свайпа (по центру) */}
      {showControls && currentPair && (
        <div className="absolute top-4 left-1/2 -translate-x-1/2 z-[990] bg-white/95 backdrop-blur-sm border border-[#EAECF0] rounded-full px-3 py-1 shadow-floating flex items-center gap-2 text-xs select-none max-w-fit pointer-events-none">
          <span className="text-text-secondary whitespace-nowrap">
            ДО · {currentPair.date_pre_sar ? currentPair.date_pre_sar.slice(5) : '12.07'}
          </span>
          <span className="w-4 h-4 rounded-full bg-[#F1F5F9] flex items-center justify-center text-text-muted font-bold text-[9px]">
            {'<->'}
          </span>
          <span className="text-text-secondary font-medium whitespace-nowrap">
            ПИК · {currentPair.date_peak_sar ? currentPair.date_peak_sar.slice(5) : '14.07'}
          </span>
        </div>
      )}

      {/* Плавающая карточка градиентной легенды с ползунком прозрачности */}
      {showControls && activeGradientConfig && (
        <div className="absolute bottom-11 left-4 z-[1000] select-none">
          {showGradientBar ? (
            <div className="bg-white/95 backdrop-blur-sm border border-[#EAECF0] rounded-xl p-2.5 shadow-floating w-64 text-xs space-y-1.5 animate-in fade-in duration-150">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5 font-semibold text-text-primary text-[11px] truncate">
                  <Droplets className="w-3.5 h-3.5 text-sky-500 shrink-0" />
                  <span className="truncate" title={activeGradientConfig.title}>
                    {activeGradientConfig.title}
                  </span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="text-[9px] font-mono text-text-muted px-1.5 py-0.5 rounded bg-slate-100 font-semibold">
                    {Math.round(gradientOpacity * 100)}%
                  </span>
                  <button
                    onClick={() => setShowGradientBar(false)}
                    className="p-0.5 text-text-muted hover:text-text-primary hover:bg-slate-100 rounded transition-colors cursor-pointer"
                    title="Свернуть панель градиента"
                  >
                    <ChevronDown className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              <div
                className="w-full h-2 rounded-full border border-black/10 shadow-inner"
                style={{ background: activeGradientConfig.gradient }}
              />

              <div className="flex justify-between items-center text-[9px] text-text-muted font-mono">
                <span>{activeGradientConfig.min}</span>
                <span>{activeGradientConfig.mid}</span>
                <span>{activeGradientConfig.max}</span>
              </div>

              {/* Встроенный ползунок прозрачности прямо в карточке карты */}
              <div className="pt-1 border-t border-slate-100 flex items-center justify-between gap-2 text-[10px] text-text-secondary">
                <span className="shrink-0 text-text-muted text-[10px]">Прозрачность:</span>
                <input
                  type="range"
                  min="10"
                  max="100"
                  step="5"
                  value={Math.round(gradientOpacity * 100)}
                  onChange={(e) => setGradientOpacity(Number(e.target.value) / 100)}
                  className="w-full h-1 bg-slate-200 rounded appearance-none cursor-pointer accent-[#0EA5E9]"
                  title={`Прозрачность: ${Math.round(gradientOpacity * 100)}%`}
                />
                <span className="font-mono text-[10px] w-6 text-right font-medium">
                  {Math.round(gradientOpacity * 100)}%
                </span>
              </div>
            </div>
          ) : (
            <button
              onClick={() => setShowGradientBar(true)}
              className="bg-white/95 backdrop-blur-sm border border-[#EAECF0] rounded-xl px-2.5 py-1 shadow-floating text-xs font-medium text-text-secondary hover:text-text-primary flex items-center gap-1.5 transition-all hover:bg-white select-none hover:scale-105 cursor-pointer"
              title="Развернуть шкалу градиента"
            >
              <Droplets className="w-3.5 h-3.5 text-sky-500" />
              <span className="text-[11px] font-semibold text-text-primary">Градиент</span>
              <span className="text-[10px] font-mono text-text-muted">
                {Math.round(gradientOpacity * 100)}%
              </span>
              <ChevronUp className="w-3.5 h-3.5 text-text-muted ml-0.5" />
            </button>
          )}
        </div>
      )}

      {/* Строка состояния карты (нижний левый угол) */}
      {showControls && (
        <div className="absolute bottom-2 left-4 z-[1000] bg-white/90 backdrop-blur-xs border border-border/80 rounded-md px-3 py-1 text-[11px] font-mono text-text-secondary flex items-center gap-3 shadow-xs">
          <span>
            {mouseCoords.lat.toFixed(4)}° N, {mouseCoords.lng.toFixed(4)}° E
          </span>
          <span className="text-border">|</span>
          <div className="flex items-center gap-1">
            <span className="border-b border-text-secondary w-8 inline-block" />
            <span>10 км</span>
          </div>
          <span className="text-border">|</span>
          <span>EPSG:32652 · Zoom {zoomLevel}</span>
        </div>
      )}
    </div>
  );
};
