import { describe, it, expect } from 'vitest';
import { cn } from '../lib/cn';

describe('cn utility (tailwind-merge + clsx)', () => {
  it('merges simple class names', () => {
    expect(cn('px-2', 'py-1')).toBe('px-2 py-1');
  });

  it('handles conditional expressions and booleans', () => {
    expect(cn('base', true && 'active', false && 'hidden')).toBe('base active');
  });

  it('ignores null, undefined, and empty string', () => {
    expect(cn('base', null, undefined, '', 'extra')).toBe('base extra');
  });

  it('correctly resolves conflicting tailwind classes', () => {
    // twMerge should keep the last conflicting utility
    expect(cn('px-2 py-1', 'px-4')).toBe('py-1 px-4');
    expect(cn('text-red-500', 'text-blue-500')).toBe('text-blue-500');
    expect(cn('bg-white', 'bg-slate-900')).toBe('bg-slate-900');
  });

  it('supports object syntax', () => {
    expect(cn({ 'bg-primary': true, 'text-white': false, 'font-bold': true })).toBe(
      'bg-primary font-bold'
    );
  });

  it('supports nested array syntax', () => {
    expect(cn(['p-4', ['m-2', ['text-sm']]])).toBe('p-4 m-2 text-sm');
  });
});
