import { describe, it, expect } from 'vitest';
import { WATER_COLORS, STATUS_COLORS } from '../lib/colors';

describe('Design System Color Palette', () => {
  describe('WATER_COLORS palette specification from frontend.md', () => {
    it('contains all 5 mandatory water classes', () => {
      const keys = Object.keys(WATER_COLORS);
      expect(keys).toEqual(['permanent', 'water_pre', 'water_peak', 'flood', 'receded']);
    });

    it('verifies permanent (постоянная вода): #3B82F6 with opacity 0.55', () => {
      expect(WATER_COLORS.permanent.color).toBe('#3B82F6');
      expect(WATER_COLORS.permanent.fillColor).toBe('#3B82F6');
      expect(WATER_COLORS.permanent.opacity).toBe(0.55);
      expect(WATER_COLORS.permanent.fillOpacity).toBe(0.55);
      expect(WATER_COLORS.permanent.name).toBe('Постоянная вода');
    });

    it('verifies water_pre (вода на «до»): #60A5FA with opacity 0.45', () => {
      expect(WATER_COLORS.water_pre.color).toBe('#60A5FA');
      expect(WATER_COLORS.water_pre.fillColor).toBe('#60A5FA');
      expect(WATER_COLORS.water_pre.opacity).toBe(0.45);
      expect(WATER_COLORS.water_pre.fillOpacity).toBe(0.45);
      expect(WATER_COLORS.water_pre.name).toBe('Вода на «до»');
    });

    it('verifies water_peak (вода на «пик»): #06B6D4 with opacity 0.50', () => {
      expect(WATER_COLORS.water_peak.color).toBe('#06B6D4');
      expect(WATER_COLORS.water_peak.fillColor).toBe('#06B6D4');
      expect(WATER_COLORS.water_peak.opacity).toBe(0.50);
      expect(WATER_COLORS.water_peak.fillOpacity).toBe(0.50);
      expect(WATER_COLORS.water_peak.name).toBe('Вода на «пик»');
    });

    it('verifies flood (новое затопление): #F97316 fill with opacity 0.70 and 2px #EA580C contour', () => {
      expect(WATER_COLORS.flood.fillColor).toBe('#F97316');
      expect(WATER_COLORS.flood.fillOpacity).toBe(0.70);
      expect(WATER_COLORS.flood.color).toBe('#EA580C');
      expect(WATER_COLORS.flood.weight).toBe(2);
      expect(WATER_COLORS.flood.name).toBe('Новое затопление');
    });

    it('verifies receded (убыль воды): #A78BFA with opacity 0.35 and dashed contour', () => {
      expect(WATER_COLORS.receded.color).toBe('#A78BFA');
      expect(WATER_COLORS.receded.fillColor).toBe('#A78BFA');
      expect(WATER_COLORS.receded.opacity).toBe(0.35);
      expect(WATER_COLORS.receded.fillOpacity).toBe(0.35);
      expect(WATER_COLORS.receded.dashArray).toBe('4, 4');
      expect(WATER_COLORS.receded.name).toBe('Убыль воды');
    });
  });

  describe('STATUS_COLORS palette from frontend.md', () => {
    it('verifies active status (в зачёте)', () => {
      expect(STATUS_COLORS.active.bg).toBe('#ECFDF5');
      expect(STATUS_COLORS.active.text).toBe('#047857');
      expect(STATUS_COLORS.active.label).toBe('В ЗАЧЁТЕ');
    });

    it('verifies baseline status (контроль)', () => {
      expect(STATUS_COLORS.baseline.bg).toBe('#F1F5F9');
      expect(STATUS_COLORS.baseline.text).toBe('#475467');
      expect(STATUS_COLORS.baseline.label).toBe('КОНТРОЛЬ');
    });

    it('verifies no_optical status (нет оптики)', () => {
      expect(STATUS_COLORS.no_optical.bg).toBe('#FEF3C7');
      expect(STATUS_COLORS.no_optical.text).toBe('#92400E');
      expect(STATUS_COLORS.no_optical.label).toBe('НЕТ ОПТИКИ');
    });

    it('verifies weak_signal status (слабый сигнал)', () => {
      expect(STATUS_COLORS.weak_signal.bg).toBe('#FEF2F2');
      expect(STATUS_COLORS.weak_signal.text).toBe('#B91C1C');
      expect(STATUS_COLORS.weak_signal.label).toBe('СЛАБЫЙ СИГНАЛ');
    });
  });
});
