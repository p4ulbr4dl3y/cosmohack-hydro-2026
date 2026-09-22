import L from 'leaflet';
import { apiClient } from '../api/client';
import type { SceneMeta } from '../types/domain';

/**
 * Подложка из реальной сцены Sentinel-1/2.
 *
 * Сцена приходит с API как PNG в границах WGS84 и кладётся в отдельную панель
 * между тайлами (z=200) и векторными слоями (z=400), поэтому маски всегда
 * читаются поверх снимка. Когда сцены нет (например, Sentinel-2 для пары без
 * оптики), функция возвращает null: карта остаётся на нейтральной подложке,
 * а не подменяет сцену посторонними тайлами.
 */
const SCENE_PANE = 'scenePane';
const SCENE_PANE_Z = 300;

function ensureScenePane(map: L.Map): string {
  if (!map.getPane(SCENE_PANE)) {
    const pane = map.createPane(SCENE_PANE);
    pane.style.zIndex = String(SCENE_PANE_Z);
    pane.style.pointerEvents = 'none';
  }
  return SCENE_PANE;
}

export interface SceneOverlay {
  layer: L.ImageOverlay;
  meta: SceneMeta;
  remove: () => void;
}

export async function loadSceneOverlay(
  map: L.Map,
  pairId: string,
  mode: string,
  window: 'peak' | 'pre' = 'peak'
): Promise<SceneOverlay | null> {
  const meta = await apiClient.fetchSceneMeta(pairId, mode, window);
  if (!meta?.bounds) return null;

  const layer = L.imageOverlay(apiClient.getSceneUrl(pairId, mode, window), meta.bounds, {
    pane: ensureScenePane(map),
    opacity: 1,
    interactive: false,
  }).addTo(map);

  return {
    layer,
    meta,
    remove: () => {
      map.removeLayer(layer);
    },
  };
}