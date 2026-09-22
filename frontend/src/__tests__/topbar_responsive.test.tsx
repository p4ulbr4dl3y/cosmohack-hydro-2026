// @vitest-environment jsdom
import { describe, it, expect, vi } from 'vitest';
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { Topbar } from '../components/layout/Topbar';

describe('Topbar responsive component', () => {
  it('renders brand logo and HydroWatch Amur text', () => {
    render(
      <MemoryRouter>
        <Topbar />
      </MemoryRouter>
    );

    expect(screen.getByText('HydroWatch')).toBeDefined();
    expect(screen.getByText('Amur')).toBeDefined();
    expect(screen.getByText('BETA')).toBeDefined();
  });

  it('toggles mobile menu drawer when hamburger button is clicked', () => {
    render(
      <MemoryRouter>
        <Topbar />
      </MemoryRouter>
    );

    const toggleBtn = screen.getByLabelText('Переключить меню');
    expect(screen.queryByText('Навигация по разделам')).toBeNull();

    fireEvent.click(toggleBtn);
    expect(screen.getByText('Навигация по разделам')).toBeDefined();
    expect(screen.getByText('Карта (Дашборд)')).toBeDefined();
    expect(screen.getByText('Сравнение до/пик')).toBeDefined();
    expect(screen.getByText('Аналитический отчёт')).toBeDefined();

    fireEvent.click(toggleBtn);
    expect(screen.queryByText('Навигация по разделам')).toBeNull();
  });

  it('calls onRefresh when refresh button is clicked', () => {
    const handleRefresh = vi.fn();
    render(
      <MemoryRouter>
        <Topbar onRefresh={handleRefresh} />
      </MemoryRouter>
    );

    const refreshBtn = screen.getByTitle('Обновить данные');
    fireEvent.click(refreshBtn);
    expect(handleRefresh).toHaveBeenCalled();
  });
});
