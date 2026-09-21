import type { LandcoverBreakdown, LandcoverItem } from '../types/domain';

/**
 * Выводит элементы отображения из агрегатов, возвращаемых отчётом API.
 *
 * Сервис отдаёт `builtup_ha` / `cropland_ha` / `natural_vegetation_ha`
 * (взаимоисключающие, в сумме дающие площадь затопления), но без `items`
 * по каждому классу. Возвращает `null`, когда в payload нет пригодных
 * агрегатов, чтобы вызывающий код мог перейти на свой набор заглушек.
 */
export function deriveLandcoverItems(
  landcover?: LandcoverBreakdown | null
): LandcoverItem[] | null {
  if (!landcover) return null;

  const classes: Array<{ class_name: string; area_ha: number }> = [
    { class_name: 'Лес / растительность', area_ha: Number(landcover.natural_vegetation_ha) || 0 },
    { class_name: 'Сельхозугодья / Пашни', area_ha: Number(landcover.cropland_ha) || 0 },
    { class_name: 'Застройка / Населенные пункты', area_ha: Number(landcover.builtup_ha) || 0 },
  ];

  const total = classes.reduce((acc, c) => acc + c.area_ha, 0);
  if (total <= 0) return null;

  return classes.map((c) => ({
    class_name: c.class_name,
    area_ha: Number(c.area_ha.toFixed(2)),
    percentage: Number(((c.area_ha / total) * 100).toFixed(1)),
  }));
}