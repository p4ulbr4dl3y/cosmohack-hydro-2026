import { apiClient } from '../api/client';
import { geojsonCache } from '../components/map/MapContainer';

let preloaded = false;

export function preloadAppCache() {
  if (preloaded || typeof window === 'undefined') return;
  preloaded = true;

  const runPreload = async () => {
    try {
      // 1. Предзагрузка метаданных пар
      const pairs = await apiClient.fetchPairs();

      // 2. Предзагрузка векторов AOI и базовой гидрографии
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

      // 3. Предзагрузка первых 3 пар (включая активную по умолчанию)
      const topPairs = (pairs || []).slice(0, 3);
      for (const p of topPairs) {
        const pId = p.pair_id;

        // Прогрев отчёта, аудита, неопределённости и sar в кэше клиента и браузера
        apiClient.fetchReport(pId).catch(() => {});
        apiClient.fetchAudit(pId).catch(() => {});
        apiClient.fetchUncertainty(pId).catch(() => {});
        apiClient.fetchSarAnalytics(pId).catch(() => {});

        // Предзагрузка GeoJSON затопления напрямую в кэш RAM
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

        // Предзагрузка метаданных оверлея и растрового PNG-изображения в кэш браузера
        apiClient.fetchOverlayMeta(pId, 'flood').then(() => {
          const img = new Image();
          img.src = apiClient.getOverlayUrl(pId, 'flood', true);
        }).catch(() => {});
      }
    } catch (err) {
      // Сбои фоновой предзагрузки не критичны
      console.warn('Background preload skipped:', err);
    }
  };

  // Запуск в период простоя или по короткому таймауту, чтобы отрисовка посадочной страницы была мгновенной на 100%
  if ('requestIdleCallback' in window) {
    (window as any).requestIdleCallback(runPreload, { timeout: 1200 });
  } else {
    setTimeout(runPreload, 150);
  }
}
