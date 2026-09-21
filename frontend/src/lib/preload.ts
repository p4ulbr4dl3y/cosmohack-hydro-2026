import { apiClient } from '../api/client';
import { geojsonCache } from '../components/map/MapContainer';

let preloaded = false;

export function preloadAppCache() {
  if (preloaded || typeof window === 'undefined') return;
  preloaded = true;

  const runPreload = async () => {
    try {
      // 1. Preload pairs metadata
      const pairs = await apiClient.fetchPairs();

      // 2. Preload AOI and Base Hydrology vectors
      if (!geojsonCache.has('aoi')) {
        apiClient.fetchAoi().then((aoi) => {
          if (aoi) geojsonCache.set('aoi', aoi);
        }).catch(() => {});
      }

      if (!geojsonCache.has('hydrography_osm')) {
        apiClient.fetchVectorLayer('hydrography_osm').then((osm) => {
          if (osm) geojsonCache.set('hydrography_osm', osm);
        }).catch(() => {});
      }

      // 3. Preload top 3 pairs (including the default active pair)
      const topPairs = (pairs || []).slice(0, 3);
      for (const p of topPairs) {
        const pId = p.pair_id;

        // Warm up report, audit, uncertainty, and sar in client & browser cache
        apiClient.fetchReport(pId).catch(() => {});
        apiClient.fetchAudit(pId).catch(() => {});
        apiClient.fetchUncertainty(pId).catch(() => {});
        apiClient.fetchSarAnalytics(pId).catch(() => {});

        // Preload flood GeoJSON directly into RAM cache
        const floodKey = `${pId}_flood`;
        if (!geojsonCache.has(floodKey)) {
          apiClient.fetchLayerGeoJson(pId, 'flood').then((gj) => {
            if (gj) geojsonCache.set(floodKey, gj);
          }).catch(() => {});
        }

        const waterPeakKey = `${pId}_water_peak`;
        if (!geojsonCache.has(waterPeakKey)) {
          apiClient.fetchLayerGeoJson(pId, 'water_peak').then((gj) => {
            if (gj) geojsonCache.set(waterPeakKey, gj);
          }).catch(() => {});
        }

        // Preload overlay metadata & raster PNG image into browser cache
        apiClient.fetchOverlayMeta(pId, 'flood').then(() => {
          const img = new Image();
          img.src = apiClient.getOverlayUrl(pId, 'flood', true);
        }).catch(() => {});
      }
    } catch (err) {
      // Background preload failures are non-critical
      console.warn('Background preload skipped:', err);
    }
  };

  // Run in idle period or short timeout so landing render is 100% instant
  if ('requestIdleCallback' in window) {
    (window as any).requestIdleCallback(runPreload, { timeout: 1200 });
  } else {
    setTimeout(runPreload, 150);
  }
}
