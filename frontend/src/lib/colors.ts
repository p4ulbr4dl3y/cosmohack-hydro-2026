export const WATER_COLORS = {
  permanent: {
    color: '#3B82F6',
    fillColor: '#3B82F6',
    opacity: 0.55,
    fillOpacity: 0.55,
    name: 'Постоянная вода',
  },
  water_pre: {
    color: '#60A5FA',
    fillColor: '#60A5FA',
    opacity: 0.45,
    fillOpacity: 0.45,
    name: 'Вода на «до»',
  },
  water_peak: {
    color: '#06B6D4',
    fillColor: '#06B6D4',
    opacity: 0.50,
    fillOpacity: 0.50,
    name: 'Вода на «пик»',
  },
  flood: {
    color: '#EA580C',
    fillColor: '#F97316',
    weight: 2,
    opacity: 0.90,
    fillOpacity: 0.70,
    name: 'Новое затопление',
  },
  receded: {
    color: '#A78BFA',
    fillColor: '#A78BFA',
    opacity: 0.35,
    fillOpacity: 0.35,
    dashArray: '4, 4',
    name: 'Убыль воды',
  },
} as const;

export type WaterClass = keyof typeof WATER_COLORS;

export const STATUS_COLORS = {
  active: {
    bg: '#ECFDF5',
    text: '#047857',
    label: 'В ЗАЧЁТЕ',
  },
  baseline: {
    bg: '#F1F5F9',
    text: '#475467',
    label: 'КОНТРОЛЬ',
  },
  no_optical: {
    bg: '#FEF3C7',
    text: '#92400E',
    label: 'НЕТ ОПТИКИ',
  },
  weak_signal: {
    bg: '#FEF2F2',
    text: '#B91C1C',
    label: 'СЛАБЫЙ СИГНАЛ',
  },
} as const;
