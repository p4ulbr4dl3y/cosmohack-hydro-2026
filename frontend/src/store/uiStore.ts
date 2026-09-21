import { create } from 'zustand';
import type { BasemapType, LayerState, GradientOverlayMode } from '../types/domain';

export type CompareMode = 'sar' | 'msi' | 'masks';

interface UiState {
  activePairId: string;
  setActivePairId: (id: string) => void;

  layers: LayerState;
  toggleLayer: (layerName: keyof Omit<LayerState, 'opacity'>) => void;
  setLayerOpacity: (opacity: number) => void;

  gradientMode: GradientOverlayMode;
  setGradientMode: (mode: GradientOverlayMode) => void;
  gradientOpacity: number;
  setGradientOpacity: (opacity: number) => void;

  basemap: BasemapType;
  setBasemap: (basemap: BasemapType) => void;

  compareMode: CompareMode;
  setCompareMode: (mode: CompareMode) => void;
  compareSplitPosition: number;
  setCompareSplitPosition: (pos: number) => void;

  mapCenter: [number, number];
  setMapCenter: (center: [number, number]) => void;
  mapZoom: number;
  setMapZoom: (zoom: number) => void;

  filterKind: 'all' | 'flood' | 'baseline';
  setFilterKind: (kind: 'all' | 'flood' | 'baseline') => void;
  filterOnlyOptical: boolean;
  setFilterOnlyOptical: (val: boolean) => void;
  searchQuery: string;
  setSearchQuery: (query: string) => void;
  sortBy: 'date' | 'area' | 'name';
  setSortBy: (sort: 'date' | 'area' | 'name') => void;

  showLegend: boolean;
  toggleLegend: () => void;
  setShowLegend: (show: boolean) => void;
}

export const useUiStore = create<UiState>((set) => ({
  activePairId: 'flood_2019_07_amur__blagoveshchensk',
  setActivePairId: (id) => set({ activePairId: id }),

  layers: {
    flood: true,
    water_peak: true,
    water_pre: true,
    permanent: true,
    receded: false,
    osm_hydro: true,
    hydrosheds: false,
    aoi_boundary: true,
    opacity: 0.6,
  },

  toggleLayer: (name) =>
    set((state) => ({
      layers: {
        ...state.layers,
        [name]: !state.layers[name],
      },
    })),

  setLayerOpacity: (opacity) =>
    set((state) => ({
      layers: {
        ...state.layers,
        opacity: Math.max(0, Math.min(1, opacity)),
      },
    })),

  gradientMode: 'flood',
  setGradientMode: (gradientMode) => set({ gradientMode }),
  gradientOpacity: 0.75,
  setGradientOpacity: (gradientOpacity) =>
    set({ gradientOpacity: Math.max(0.1, Math.min(1, gradientOpacity)) }),

  basemap: 'msi_true',
  setBasemap: (basemap) => set({ basemap }),

  compareMode: 'sar',
  setCompareMode: (compareMode) => set({ compareMode }),
  compareSplitPosition: 50,
  setCompareSplitPosition: (compareSplitPosition) => set({ compareSplitPosition }),

  mapCenter: [50.28, 127.54],
  setMapCenter: (mapCenter) => set({ mapCenter }),
  mapZoom: 10,
  setMapZoom: (mapZoom) => set({ mapZoom }),

  filterKind: 'all',
  setFilterKind: (filterKind) => set({ filterKind }),
  filterOnlyOptical: false,
  setFilterOnlyOptical: (filterOnlyOptical) => set({ filterOnlyOptical }),
  searchQuery: '',
  setSearchQuery: (searchQuery) => set({ searchQuery }),
  sortBy: 'date',
  setSortBy: (sortBy) => set({ sortBy }),

  showLegend: true,
  toggleLegend: () => set((state) => ({ showLegend: !state.showLegend })),
  setShowLegend: (showLegend) => set({ showLegend }),
}));
