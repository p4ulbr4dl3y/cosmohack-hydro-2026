import { describe, it, expect } from 'vitest';
import { formatHa, formatKm2, formatPercent, formatNumber } from '../lib/format';

describe('format utilities', () => {
  describe('formatNumber', () => {
    it('formats real numbers with decimal comma and narrow non-breaking space', () => {
      // Узкий неразрывный пробел \u202F
      expect(formatNumber(2847.3, 1)).toBe('2\u202F847,3');
      expect(formatNumber(22.86, 2)).toBe('22,86');
      expect(formatNumber(0.23, 2)).toBe('0,23');
      expect(formatNumber(1234567.89, 2)).toBe('1\u202F234\u202F567,89');
    });

    it('formats integers without decimal point when decimals is 0', () => {
      expect(formatNumber(100, 0)).toBe('100');
      expect(formatNumber(1250, 0)).toBe('1\u202F250');
      expect(formatNumber(1000000, 0)).toBe('1\u202F000\u202F000');
    });

    it('handles zero correctly', () => {
      expect(formatNumber(0, 1)).toBe('0,0');
      expect(formatNumber(0, 0)).toBe('0');
      expect(formatNumber(0, 2)).toBe('0,00');
    });

    it('handles null, undefined and NaN edge cases returning dash', () => {
      expect(formatNumber(null)).toBe('—');
      expect(formatNumber(undefined)).toBe('—');
      expect(formatNumber(NaN)).toBe('—');
      expect(formatNumber(Number.NaN)).toBe('—');
    });
  });

  describe('formatHa', () => {
    it('formats real hectare values from HydroWatch dataset', () => {
      expect(formatHa(2847.3)).toBe('2\u202F847,3 га');
      expect(formatHa(1614.38, 2)).toBe('1\u202F614,38 га');
      expect(formatHa(7762.73, 1)).toBe('7\u202F762,7 га');
      expect(formatHa(0)).toBe('0,0 га');
    });

    it('handles null, undefined, and NaN edge cases', () => {
      expect(formatHa(null)).toBe('—');
      expect(formatHa(undefined)).toBe('—');
      expect(formatHa(NaN)).toBe('—');
    });
  });

  describe('formatKm2', () => {
    it('formats real square kilometer values with default 2 decimals', () => {
      expect(formatKm2(22.86)).toBe('22,86 км²');
      expect(formatKm2(1585.927, 2)).toBe('1\u202F585,93 км²');
      expect(formatKm2(1245.0, 0)).toBe('1\u202F245 км²');
      expect(formatKm2(0)).toBe('0,00 км²');
    });

    it('handles null, undefined, and NaN edge cases', () => {
      expect(formatKm2(null)).toBe('—');
      expect(formatKm2(undefined)).toBe('—');
      expect(formatKm2(NaN)).toBe('—');
    });
  });

  describe('formatPercent', () => {
    it('formats real percentage values with % symbol', () => {
      expect(formatPercent(0.23)).toBe('0,23%');
      expect(formatPercent(14.97)).toBe('14,97%');
      expect(formatPercent(100.0, 1)).toBe('100,0%');
      expect(formatPercent(0)).toBe('0,00%');
    });

    it('handles null, undefined, and NaN edge cases', () => {
      expect(formatPercent(null)).toBe('—');
      expect(formatPercent(undefined)).toBe('—');
      expect(formatPercent(NaN)).toBe('—');
    });
  });
});
