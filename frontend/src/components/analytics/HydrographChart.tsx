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
}

export const HydrographChart: React.FC<HydrographChartProps> = () => {
  const data = [
    { date: '12.07', pre: 3200, peak: 4500 },
    { date: '13.07', pre: 7800, peak: 11200 },
    { date: '14.07', pre: 9600, peak: 14800 },
    { date: '15.07', pre: 8500, peak: 10400 },
  ];

  return (
    <div className="bg-white border border-[#EAECF0] rounded-xl p-4 shadow-card">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-semibold text-text-primary">Гидрограф</span>
        <span className="text-[11px] text-text-muted font-mono">Δt S1↔S2 = 2 суток</span>
      </div>

      <div className="flex items-center gap-3 text-[11px] text-text-secondary mb-3">
        <div className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-[#60A5FA]" />
          <span>pre</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-[#06B6D4]" />
          <span>peak</span>
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
              tickFormatter={(v) => (v === 0 ? '0' : `${v / 1000}k`)}
            />
            <Tooltip
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
              dataKey="pre"
              stroke="#60A5FA"
              strokeWidth={2}
              dot={{ r: 3, fill: '#60A5FA' }}
            />
            <Line
              type="monotone"
              dataKey="peak"
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
