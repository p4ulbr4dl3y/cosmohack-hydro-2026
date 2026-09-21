import React from 'react';

interface StatusBarProps {
  coords?: { lat: number; lng: number; zoom: number };
}

export const StatusBar: React.FC<StatusBarProps> = ({ coords }) => {
  const latStr = coords ? `${coords.lat.toFixed(4)}° N` : '50.2831° N';
  const lngStr = coords ? `${coords.lng.toFixed(4)}° E` : '127.5342° E';
  const zoomStr = coords ? `Zoom ${coords.zoom}` : 'Zoom 11';

  return (
    <footer className="h-7 bg-surface border-t border-border flex items-center justify-between px-4 text-[11px] text-text-muted font-mono z-40 select-none">
      <div className="flex items-center gap-3">
        <span>{latStr}, {lngStr}</span>
        <span>·</span>
        <span>10 км</span>
        <span>·</span>
        <span>EPSG:32652</span>
        <span>·</span>
        <span>{zoomStr}</span>
      </div>

      <div className="flex items-center gap-3">
        <span>Обработка: 12,4 с</span>
        <span>·</span>
        <span>Память: 1,8 ГБ</span>
      </div>

      <div className="flex items-center gap-1.5 font-sans font-medium text-emerald-700">
        <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
        <span>API: online</span>
      </div>
    </footer>
  );
};
