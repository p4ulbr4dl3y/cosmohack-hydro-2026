/**
 * Форматирует числа согласно HydroWatch Amur Design System.
 * Использует узкий неразрывный пробел (\u202F) для тысяч и запятую для десятичного разделителя.
 */

export function formatNumber(val: number | null | undefined, decimals = 1): string {
  if (val === null || val === undefined || isNaN(val)) return '—';
  
  const fixed = val.toFixed(decimals);
  const [intPart, decPart] = fixed.split('.');
  
  // Группировка тысяч узким неразрывным пробелом
  const formattedInt = intPart.replace(/\B(?=(\d{3})+(?!\d))/g, '\u202F');
  
  return decPart !== undefined && decimals > 0 
    ? `${formattedInt},${decPart}` 
    : formattedInt;
}

export function formatHa(val: number | null | undefined, decimals = 1): string {
  if (val === null || val === undefined || isNaN(val)) return '—';
  return `${formatNumber(val, decimals)} га`;
}

export function formatKm2(val: number | null | undefined, decimals = 2): string {
  if (val === null || val === undefined || isNaN(val)) return '—';
  return `${formatNumber(val, decimals)} км²`;
}

export function formatPercent(val: number | null | undefined, decimals = 2): string {
  if (val === null || val === undefined || isNaN(val)) return '—';
  return `${formatNumber(val, decimals)}%`;
}
