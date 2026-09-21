import React, { useEffect, useState } from 'react';
import { Leaf, Trees, Info } from 'lucide-react';
import { apiClient } from '../../api/client';
import type { FloodCarbonImpact } from '../../types/domain';

interface CarbonMetricsCardProps {
  pairId?: string;
  isLoading?: boolean;
}

export const CarbonMetricsCard: React.FC<CarbonMetricsCardProps> = ({ pairId, isLoading = false }) => {
  const [carbon, setCarbon] = useState<FloodCarbonImpact | null>(null);
  const [loadingData, setLoadingData] = useState(false);

  useEffect(() => {
    if (!pairId) return;
    let isMounted = true;
    setLoadingData(true);

    apiClient
      .fetchCarbonImpact(pairId)
      .then((res) => {
        if (isMounted) setCarbon(res);
      })
      .catch(console.error)
      .finally(() => {
        if (isMounted) setLoadingData(false);
      });

    return () => {
      isMounted = false;
    };
  }, [pairId]);

  if (isLoading || loadingData) {
    return (
      <div className="bg-white border border-[#EAECF0] rounded-xl p-4 shadow-2xs animate-pulse">
        <div className="h-4 bg-slate-200 rounded w-1/2 mb-2" />
        <div className="grid grid-cols-2 gap-2 mb-2">
          <div className="h-8 bg-slate-100 rounded" />
          <div className="h-8 bg-slate-100 rounded" />
        </div>
      </div>
    );
  }

  if (!carbon) return null;

  const { credit_potential } = carbon;

  return (
    <div className="bg-white border border-emerald-200 rounded-xl p-4 shadow-2xs text-xs space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5 font-semibold text-emerald-950">
          <Leaf className="w-4 h-4 text-emerald-600" />
          <span>Углеродный ущерб и ESG (IPCC)</span>
        </div>
        <span className="px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700 text-[10px] font-bold border border-emerald-200">
          CF = 0.47
        </span>
      </div>

      {/* Primary Metrics Grid */}
      <div className="grid grid-cols-2 gap-2">
        <div className="bg-emerald-50/50 border border-emerald-100 rounded-lg p-2.5">
          <div className="text-[10px] text-emerald-800 uppercase tracking-wider font-semibold">
            Потери углерода (C)
          </div>
          <div className="text-base font-black text-emerald-950">
            {carbon.carbon_loss_tC.toLocaleString('ru-RU')} <span className="text-xs font-normal text-text-muted">т C</span>
          </div>
          <div className="text-[10px] text-text-secondary mt-0.5">
            Биомасса: {carbon.biomass_loss_dry_matter_t.toLocaleString('ru-RU')} т сух. в-ва
          </div>
        </div>

        <div className="bg-amber-50/50 border border-amber-200/80 rounded-lg p-2.5">
          <div className="text-[10px] text-amber-800 uppercase tracking-wider font-semibold">
            Эквивалент CO₂-экв. (E)
          </div>
          <div className="text-base font-black text-amber-950">
            {carbon.emissions_equivalent_tCO2e.toLocaleString('ru-RU')}{' '}
            <span className="text-xs font-normal text-text-muted">т CO₂e</span>
          </div>
          <div className="text-[10px] text-text-secondary mt-0.5">
            Молярное отн. 44/12
          </div>
        </div>
      </div>

      {/* Sector Breakdown */}
      <div className="flex items-center justify-between text-[11px] bg-slate-50 border border-slate-200/60 rounded-lg px-2.5 py-2">
        <div className="flex items-center gap-1.5 text-text-secondary">
          <Trees className="w-3.5 h-3.5 text-emerald-600" />
          <span>Сельхоз / Лес:</span>
        </div>
        <div className="font-medium text-slate-800">
          {carbon.cropland_loss_tC.toFixed(1)} т C (поля) · {carbon.forest_loss_tC.toFixed(1)} т C (леса)
        </div>
      </div>

      {/* Carbon Credits Potential */}
      {credit_potential && credit_potential.is_available && (
        <div className="border-t border-slate-100 pt-2 space-y-1.5">
          <div className="flex items-center justify-between text-[11px]">
            <span className="text-text-secondary">Потенциал единиц (Q):</span>
            <span className="font-bold text-slate-900 font-mono">
              {credit_potential.Q_credits.toLocaleString('ru-RU')} ед. CO₂e
            </span>
          </div>
          <div className="flex items-center justify-between text-[10px] text-text-secondary">
            <span>Вычет неопредел. (UNC):</span>
            <span>{(credit_potential.UNC_deduction_rate * 100).toFixed(0)}% (порог 10%)</span>
          </div>
          <div className="flex items-center justify-between text-[10px] text-text-secondary">
            <span>Буферный резерв риска (B):</span>
            <span>15% ({credit_potential.buffer_reserve_B_tCO2e.toFixed(1)} т CO₂e)</span>
          </div>

          {/* Pricing Scenarios */}
          {credit_potential.valuations_rub && (
            <div className="grid grid-cols-3 gap-1 pt-1 text-center">
              <div className="bg-slate-50 border border-slate-200/80 rounded py-1 px-0.5">
                <div className="text-[9px] text-text-muted">500 ₽/ед.</div>
                <div className="text-[10px] font-bold text-slate-800">
                  {((credit_potential.valuations_rub[500] || credit_potential.valuations_rub['500'] || 0) / 1000).toFixed(0)} тыс. ₽
                </div>
              </div>
              <div className="bg-emerald-50 border border-emerald-200/80 rounded py-1 px-0.5">
                <div className="text-[9px] text-emerald-800 font-semibold">1 500 ₽/ед.</div>
                <div className="text-[10px] font-bold text-emerald-900">
                  {((credit_potential.valuations_rub[1500] || credit_potential.valuations_rub['1500'] || 0) / 1000).toFixed(0)} тыс. ₽
                </div>
              </div>
              <div className="bg-slate-50 border border-slate-200/80 rounded py-1 px-0.5">
                <div className="text-[9px] text-text-muted">4 000 ₽/ед.</div>
                <div className="text-[10px] font-bold text-slate-800">
                  {((credit_potential.valuations_rub[4000] || credit_potential.valuations_rub['4000'] || 0) / 1000).toFixed(0)} тыс. ₽
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Note */}
      <div className="flex items-start gap-1.5 text-[10px] text-text-muted pt-1">
        <Info className="w-3 h-3 text-emerald-600 shrink-0 mt-0.5" />
        <span className="leading-tight">
          Расчет выполнен по стандарту IPCC (CF=0.47, 44/12, stock difference) с учетом риска повторного затопления.
        </span>
      </div>
    </div>
  );
};
