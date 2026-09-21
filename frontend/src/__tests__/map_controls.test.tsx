// @vitest-environment jsdom
import { describe, it, expect, beforeEach } from 'vitest';
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { Legend } from '../components/map/Legend';
import { LayerControl } from '../components/map/LayerControl';
import { useUiStore } from '../store/uiStore';

describe('Legend component', () => {
  beforeEach(() => {
    useUiStore.getState().setShowLegend(true);
  });

  it('renders open legend with all water categories by default', () => {
    render(<Legend aoiKm2={1500} />);

    expect(screen.getByText('Легенда карты')).toBeDefined();
    expect(screen.getByText('Новое затопление (flood)')).toBeDefined();
    expect(screen.getByText('Вода на пик')).toBeDefined();
    expect(screen.getByText('Вода на до')).toBeDefined();
    expect(screen.getByText('Постоянная вода')).toBeDefined();
  });

  it('can be collapsed and displays floating toggle button', () => {
    render(<Legend aoiKm2={1500} />);

    const closeBtn = screen.getByTitle('Скрыть легенду');
    fireEvent.click(closeBtn);

    expect(useUiStore.getState().showLegend).toBe(false);
  });

  it('re-expands when floating toggle button is clicked', () => {
    useUiStore.getState().setShowLegend(false);
    render(<Legend aoiKm2={1500} />);

    const showBtn = screen.getByTitle('Показать легенду');
    fireEvent.click(showBtn);

    expect(useUiStore.getState().showLegend).toBe(true);
  });
});

describe('LayerControl component', () => {
  beforeEach(() => {
    useUiStore.getState().setShowLegend(true);
  });

  it('renders LayerControl header and checkboxes', () => {
    render(<LayerControl />);

    expect(screen.getByText('СЛОИ')).toBeDefined();
    expect(screen.getByText('Маски затопления')).toBeDefined();
    expect(screen.getByText('Новое затопление')).toBeDefined();
    expect(screen.getByText('Вода на пик')).toBeDefined();
    expect(screen.getByText('Подложка')).toBeDefined();
    expect(screen.getByText('Векторы')).toBeDefined();
  });

  it('toggles layer state when checkbox is changed', () => {
    render(<LayerControl />);

    const floodCheckboxes = screen.getAllByRole('checkbox');
    expect(floodCheckboxes.length).toBeGreaterThan(0);

    const initial = useUiStore.getState().layers.flood;
    fireEvent.click(floodCheckboxes[0]);
    expect(useUiStore.getState().layers.flood).toBe(!initial);
  });

  it('allows collapsing and expanding the layers dropdown', () => {
    render(<LayerControl />);

    const headerBtn = screen.getByRole('button', { name: /СЛОИ/i });
    fireEvent.click(headerBtn); // сворачивание
    expect(screen.queryByText('Маски затопления')).toBeNull();

    fireEvent.click(headerBtn); // разворачивание
    expect(screen.getByText('Маски затопления')).toBeDefined();
  });
});
