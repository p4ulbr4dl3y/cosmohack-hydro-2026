import React, { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
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

const geojsonCache = new Map<string, any>();

export const MapContainer: React.FC<MapContainerProps> = ({
  currentPair,
  interactive = true,
  showControls = true,
  className = '',
}) => {
  const mapRef = useRef<HTMLDivElement>(null);
  const leafletMap = useRef<L.Map | null>(null);
  const tileLayerRef = useRef<L.TileLayer | null>(null);

  // Layer groups
  const aoiLayerGroup = useRef<L.GeoJSON | null>(null);
  const floodLayerGroup = useRef<L.GeoJSON | null>(null);
  const waterPeakLayerGroup = useRef<L.GeoJSON | null>(null);
  const waterPreLayerGroup = useRef<L.GeoJSON | null>(null);
  const osmHydroLayerGroup = useRef<L.GeoJSON | null>(null);
  const hydroshedsLayerGroup = useRef<L.GeoJSON | null>(null);

  const [mouseCoords, setMouseCoords] = useState<{ lat: number; lng: number }>({
    lat: 50.2899,
    lng: 127.5378,
  });
  const [zoomLevel, setZoomLevel] = useState<number>(10);
  const [aoiFeatures, setAoiFeatures] = useState<any>(null);

  const { layers, basemap, activePairId } = useUiStore();
  const effectivePairId = currentPair?.pair_id || activePairId;

  // Initialize Leaflet Map
  useEffect(() => {
    if (!mapRef.current || leafletMap.current) return;

    const map = L.map(mapRef.current, {
      preferCanvas: true,
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
    };
  }, [interactive]);

  // Update Basemap Tiles
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

  // Load AOI Polygons once (with caching)
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

  // Render AOI vector layer and fit bounds when pair or AOI changes
  useEffect(() => {
    const map = leafletMap.current;
    if (!map || !aoiFeatures) return;

    if (aoiLayerGroup.current) {
      map.removeLayer(aoiLayerGroup.current);
      aoiLayerGroup.current = null;
    }

    if (!layers.aoi_boundary) return;

    const layer = L.geoJSON(aoiFeatures, {
      style: (feature) => {
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
    }).addTo(map);

    aoiLayerGroup.current = layer;

    // Fit bounds to current AOI if found
    if (currentPair?.aoi_id) {
      const matchFeat = aoiFeatures.features?.find(
        (f: any) => f.properties?.aoi_id === currentPair.aoi_id
      );
      if (matchFeat) {
        const tempLayer = L.geoJSON(matchFeat);
        const b = tempLayer.getBounds();
        if (b.isValid()) {
          map.fitBounds(b, { padding: [40, 40], maxZoom: 12 });
        }
      } else if (currentPair.bounds_4326) {
        const [minX, minY, maxX, maxY] = currentPair.bounds_4326;
        map.fitBounds(
          [
            [minY, minX],
            [maxY, maxX],
          ],
          { padding: [40, 40], maxZoom: 12 }
        );
      }
    }
  }, [aoiFeatures, currentPair, layers.aoi_boundary]);

  // Load and render OSM Hydrography
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
        style: {
          color: '#3B82F6',
          weight: 1.5,
          opacity: 0.7,
          fillColor: '#60A5FA',
          fillOpacity: 0.3,
        },
      }).addTo(map);
      osmHydroLayerGroup.current = layer;
      return;
    }

    apiClient.fetchVectorLayer('hydrography_osm').then((geo) => {
      if (geo && leafletMap.current) {
        geojsonCache.set('hydrography_osm', geo);
        const layer = L.geoJSON(geo, {
          style: {
            color: '#3B82F6',
            weight: 1.5,
            opacity: 0.7,
            fillColor: '#60A5FA',
            fillOpacity: 0.3,
          },
        }).addTo(leafletMap.current);
        osmHydroLayerGroup.current = layer;
      }
    }).catch(() => {});
  }, [layers.osm_hydro]);

  // Load and render HydroSHEDS basins
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
        style: {
          color: '#8B5CF6',
          weight: 1.5,
          dashArray: '3, 4',
          opacity: 0.6,
          fillColor: '#C4B5FD',
          fillOpacity: 0.08,
        },
      }).addTo(map);
      hydroshedsLayerGroup.current = layer;
      return;
    }

    apiClient.fetchVectorLayer('basins_hydrosheds').then((geo) => {
      if (geo && leafletMap.current) {
        geojsonCache.set('basins_hydrosheds', geo);
        const layer = L.geoJSON(geo, {
          style: {
            color: '#8B5CF6',
            weight: 1.5,
            dashArray: '3, 4',
            opacity: 0.6,
            fillColor: '#C4B5FD',
            fillOpacity: 0.08,
          },
        }).addTo(leafletMap.current);
        hydroshedsLayerGroup.current = layer;
      }
    }).catch(() => {});
  }, [layers.hydrosheds]);

  // Load Flood & Water mask layers for pairId (ONLY when pairId changes)
  useEffect(() => {
    const map = leafletMap.current;
    if (!map || !effectivePairId) return;

    // Clear previous mask layers
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
      const gjLayer = L.geoJSON(geojson, {
        style: {
          color: colorCfg.color,
          weight: (colorCfg as any).weight || 1,
          fillColor: colorCfg.fillColor,
          fillOpacity: (colorCfg.fillOpacity || 0.5) * layers.opacity,
          opacity: (colorCfg.opacity || 0.8) * layers.opacity,
        },
      });

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
    };

    loadMask('flood');
    loadMask('water_peak');
    loadMask('water_pre');

    return () => {
      isMounted = false;
    };
  }, [effectivePairId]);

  // Fast style update for opacity without refetching or rebuilding layers
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

  // Fast toggle for flood layer
  useEffect(() => {
    const map = leafletMap.current;
    if (!map || !floodLayerGroup.current) return;
    if (layers.flood && !map.hasLayer(floodLayerGroup.current)) {
      map.addLayer(floodLayerGroup.current);
    } else if (!layers.flood && map.hasLayer(floodLayerGroup.current)) {
      map.removeLayer(floodLayerGroup.current);
    }
  }, [layers.flood]);

  // Fast toggle for water_peak layer
  useEffect(() => {
    const map = leafletMap.current;
    if (!map || !waterPeakLayerGroup.current) return;
    if (layers.water_peak && !map.hasLayer(waterPeakLayerGroup.current)) {
      map.addLayer(waterPeakLayerGroup.current);
    } else if (!layers.water_peak && map.hasLayer(waterPeakLayerGroup.current)) {
      map.removeLayer(waterPeakLayerGroup.current);
    }
  }, [layers.water_peak]);

  // Fast toggle for water_pre layer
  useEffect(() => {
    const map = leafletMap.current;
    if (!map || !waterPreLayerGroup.current) return;
    if (layers.water_pre && !map.hasLayer(waterPreLayerGroup.current)) {
      map.addLayer(waterPreLayerGroup.current);
    } else if (!layers.water_pre && map.hasLayer(waterPreLayerGroup.current)) {
      map.removeLayer(waterPreLayerGroup.current);
    }
  }, [layers.water_pre]);

  return (
    <div className={`relative w-full h-full overflow-hidden ${className}`}>
      {/* Map Root */}
      <div ref={mapRef} className="w-full h-full z-0" />

      {/* Floating LayerControl (Top Right) */}
      {showControls && (
        <div className="absolute top-4 right-4 z-[1000]">
          <LayerControl />
        </div>
      )}

      {/* Floating Legend (Bottom Right) */}
      {showControls && (
        <div className="absolute bottom-4 right-4 z-[1000]">
          <Legend aoiKm2={currentPair?.aoi_km2 || 1245} />
        </div>
      )}

      {/* Floating Swipe Pill (Center) */}
      {showControls && currentPair && (
        <div className="absolute top-4 left-1/2 -translate-x-1/2 z-[990] bg-white/95 backdrop-blur-sm border border-[#EAECF0] rounded-full px-3 py-1 shadow-floating flex items-center gap-2 text-xs select-none max-w-fit pointer-events-none">
          <span className="text-text-secondary whitespace-nowrap">
            ДО · {currentPair.date_pre_sar ? currentPair.date_pre_sar.slice(5) : '12.07'}
          </span>
          <span className="w-4 h-4 rounded-full bg-[#F1F5F9] flex items-center justify-center text-text-muted font-bold text-[9px]">
            ↔
          </span>
          <span className="text-text-secondary font-medium whitespace-nowrap">
            ПИК · {currentPair.date_peak_sar ? currentPair.date_peak_sar.slice(5) : '14.07'}
          </span>
        </div>
      )}

      {/* Map Status Bar (Bottom Left) */}
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
