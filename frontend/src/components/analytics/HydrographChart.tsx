import React from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';

interface HydrographChartProps {
  datePre?: string;
  datePeak?: string;
  waterPreHa?: number;
  waterPeakHa?: number;
}

function shortDate(iso?: string): string | null {
  if (!iso) return null;
  const [, month, day] = iso.split('-');
  if (!month || !day) return null;
  return `${day}.${month}`;
}

function daysBetween(pre?: string, peak?: string): number | null {
  if (!pre || !peak) return null;
  const start = new Date(pre).getTime();
  const end = new Date(peak).getTime();
  if (Number.isNaN(start) || Number.isNaN(end)) return null;
  return Math.round((end - start) / 86_400_000);
}

export const HydrographChart: React.FC<HydrographChartProps> = ({
  datePre,
  datePeak,
  waterPreHa,
  waterPeakHa,
}) => {
  const preLabel = shortDate(datePre) ?? 'до';
  const peakLabel = shortDate(datePeak) ?? 'пик';
  const delta = daysBetween(datePre, datePeak);

  // Строятся только реальные водные контуры SAR; синтетической интерполяции нет.
  const data = React.useMemo(() => {
    const points: Array<{ date: string; water: number }> = [];
    if (typeof waterPreHa === 'number') points.push({ date: preLabel, water: waterPreHa });
    if (typeof waterPeakHa === 'number') points.push({ date: peakLabel, water: waterPeakHa });
    return points;
  }, [preLabel, peakLabel, waterPreHa, waterPeakHa]);

  if (data.length < 2) {
    return (
      <div className="bg-white border border-[#EAECF0] rounded-xl p-4 shadow-card">
        <div className="text-xs font-semibold text-text-primary mb-2">Гидрограф</div>
        <div className="h-28 w-full flex items-center justify-center text-[11px] text-text-muted">
          Недостаточно данных для построения гидрографа
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white border border-[#EAECF0] rounded-xl p-4 shadow-card">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-semibold text-text-primary">Гидрограф</span>
        {delta !== null && (
          <span className="text-[11px] text-text-muted font-mono">SAR: {delta} суток</span>
        )}
      </div>

      <div className="flex items-center gap-3 text-[11px] text-text-secondary mb-3">
        <div className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-[#06B6D4]" />
          <span>водное зеркало, га</span>
        </div>
      </div>

      <div className="h-28 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 5, right: 5, left: -25, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#F1F5F9" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 10, fill: '#94A3B8' }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              tick={{ fontSize: 10, fill: '#94A3B8' }}
              axisLine={false}
              tickLine={false}
              domain={['auto', 'auto']}
              tickFormatter={(v) => (v === 0 ? '0' : `${Math.round(v / 1000)}k`)}
            />
            <Tooltip
              formatter={(v: number) => [`${v.toLocaleString('ru-RU')} га`, 'зеркало']}
              contentStyle={{
                backgroundColor: '#0F172A',
                borderRadius: '6px',
                border: 'none',
                color: '#fff',
                fontSize: '11px',
              }}
            />
            <Line
              type="monotone"
              dataKey="water"
              stroke="#06B6D4"
              strokeWidth={2}
              dot={{ r: 3, fill: '#06B6D4' }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};