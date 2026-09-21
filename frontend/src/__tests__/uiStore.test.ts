import { describe, it, expect, beforeEach } from 'vitest';
import { useUiStore } from '../store/uiStore';

describe('uiStore state management', () => {
  beforeEach(() => {
    // Сброс к значениям по умолчанию
    const store = useUiStore.getState();
    store.setActivePairId('flood_2019_07_amur__blagoveshchensk');
    store.setBasemap('msi_true');
    store.setCompareMode('sar');
    store.setCompareSplitPosition(50);
    store.setMapCenter([50.28, 127.54]);
    store.setMapZoom(10);
    store.setFilterKind('all');
    store.setFilterOnlyOptical(false);
    store.setSearchQuery('');
    store.setSortBy('date');
    store.setShowLegend(true);
    store.setLayerOpacity(0.6);
  });

  it('initializes with expected default values', () => {
    const state = useUiStore.getState();
    expect(state.activePairId).toBe('flood_2019_07_amur__blagoveshchensk');
    expect(state.layers.flood).toBe(true);
    expect(state.layers.water_peak).toBe(true);
    expect(state.layers.receded).toBe(false);
    expect(state.layers.opacity).toBe(0.6);
    expect(state.basemap).toBe('msi_true');
    expect(state.showLegend).toBe(true);
  });

  it('updates activePairId correctly', () => {
    const { setActivePairId } = useUiStore.getState();
    setActivePairId('flood_2021_06_amur__blagoveshchensk');
    expect(useUiStore.getState().activePairId).toBe('flood_2021_06_amur__blagoveshchensk');
  });

  it('toggles map layers on and off', () => {
    const { toggleLayer } = useUiStore.getState();

    expect(useUiStore.getState().layers.flood).toBe(true);
    toggleLayer('flood');
    expect(useUiStore.getState().layers.flood).toBe(false);
    toggleLayer('flood');
    expect(useUiStore.getState().layers.flood).toBe(true);

    expect(useUiStore.getState().layers.receded).toBe(false);
    toggleLayer('receded');
    expect(useUiStore.getState().layers.receded).toBe(true);
  });

  it('clamps layer opacity within 0.0 and 1.0', () => {
    const { setLayerOpacity } = useUiStore.getState();

    setLayerOpacity(0.8);
    expect(useUiStore.getState().layers.opacity).toBe(0.8);

    setLayerOpacity(-0.5);
    expect(useUiStore.getState().layers.opacity).toBe(0);

    setLayerOpacity(1.5);
    expect(useUiStore.getState().layers.opacity).toBe(1);
  });

  it('switches basemap options', () => {
    const { setBasemap } = useUiStore.getState();

    setBasemap('sar_vh');
    expect(useUiStore.getState().basemap).toBe('sar_vh');

    setBasemap('msi_true');
    expect(useUiStore.getState().basemap).toBe('msi_true');

    setBasemap('msi_false');
    expect(useUiStore.getState().basemap).toBe('msi_false');
  });

  it('switches compare mode and updates slider position', () => {
    const { setCompareMode, setCompareSplitPosition } = useUiStore.getState();

    setCompareMode('msi');
    expect(useUiStore.getState().compareMode).toBe('msi');

    setCompareMode('masks');
    expect(useUiStore.getState().compareMode).toBe('masks');

    setCompareSplitPosition(75);
    expect(useUiStore.getState().compareSplitPosition).toBe(75);
  });

  it('updates mapCenter and mapZoom', () => {
    const { setMapCenter, setMapZoom } = useUiStore.getState();

    setMapCenter([51.25, 128.15]);
    expect(useUiStore.getState().mapCenter).toEqual([51.25, 128.15]);

    setMapZoom(12);
    expect(useUiStore.getState().mapZoom).toBe(12);
  });

  it('controls legend collapse and visibility', () => {
    const { toggleLegend, setShowLegend } = useUiStore.getState();

    expect(useUiStore.getState().showLegend).toBe(true);
    toggleLegend();
    expect(useUiStore.getState().showLegend).toBe(false);
    toggleLegend();
    expect(useUiStore.getState().showLegend).toBe(true);

    setShowLegend(false);
    expect(useUiStore.getState().showLegend).toBe(false);
  });

  it('manages filter and search query states', () => {
    const { setFilterKind, setFilterOnlyOptical, setSearchQuery, setSortBy } =
      useUiStore.getState();

    setFilterKind('flood');
    expect(useUiStore.getState().filterKind).toBe('flood');

    setFilterKind('baseline');
    expect(useUiStore.getState().filterKind).toBe('baseline');

    setFilterOnlyOptical(true);
    expect(useUiStore.getState().filterOnlyOptical).toBe(true);

    setSearchQuery('Благовещенск');
    expect(useUiStore.getState().searchQuery).toBe('Благовещенск');

    setSortBy('area');
    expect(useUiStore.getState().sortBy).toBe('area');

    setSortBy('name');
    expect(useUiStore.getState().sortBy).toBe('name');
  });
});
