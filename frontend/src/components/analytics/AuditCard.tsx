import React, { useState } from 'react';
import type { HydroAuditCertificate } from '../../types/domain';
import { ShieldCheck, Copy, Check, Download, ChevronDown, ChevronUp, Hash, FileCode2 } from 'lucide-react';

interface AuditCardProps {
  audit: HydroAuditCertificate | null;
  isLoading?: boolean;
}

export const AuditCard: React.FC<AuditCardProps> = ({ audit, isLoading }) => {
  const [copied, setCopied] = useState(false);
  const [expanded, setExpanded] = useState(false);

  if (isLoading) {
    return (
      <div className="bg-white border border-[#EAECF0] rounded-xl p-3.5 animate-pulse space-y-2">
        <div className="h-4 bg-slate-200 rounded w-1/2"></div>
        <div className="h-8 bg-slate-100 rounded"></div>
      </div>
    );
  }

  if (!audit) return null;

  const rootHash = audit.merkle_root_sha256 || audit.merkle_root || audit.signature_hash || '';

  const findLeafHash = (keyPart: string): string => {
    if (!audit.leaves || !Array.isArray(audit.leaves)) return '';
    const leaf = audit.leaves.find(
      (l) =>
        (l.key && l.key.toLowerCase().includes(keyPart)) ||
        (l.name && l.name.toLowerCase().includes(keyPart)) ||
        (l.description && l.description.toLowerCase().includes(keyPart))
    );
    return leaf?.hash || '';
  };

  const inputsHash = audit.inputs_hash_sha256 || findLeafHash('input') || audit.leaves?.[0]?.hash || '';
  const paramsHash = audit.parameters_hash_sha256 || findLeafHash('param') || audit.leaves?.[1]?.hash || '';
  const resultsHash =
    audit.results_hash_sha256 || findLeafHash('result') || findLeafHash('hydro') || audit.leaves?.[2]?.hash || '';
  const sigHash = audit.signature_hash || '';
  const isVerified = audit.verified !== undefined ? Boolean(audit.verified) : audit.status === 'VERIFIED';
  const issuedDate = audit.issued_at || audit.timestamp;

  const handleCopyHash = () => {
    if (!rootHash) return;
    navigator.clipboard.writeText(rootHash);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownloadCert = () => {
    const certPayload = {
      ...audit,
      merkle_root_sha256: rootHash,
      inputs_hash_sha256: inputsHash,
      parameters_hash_sha256: paramsHash,
      results_hash_sha256: resultsHash,
      verified: isVerified,
    };
    const blob = new Blob([JSON.stringify(certPayload, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `audit_${audit.pair_id || 'certificate'}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const shortHash = (h?: string | null) => {
    if (!h || typeof h !== 'string') return '—';
    if (h.length <= 16) return h;
    return `${h.substring(0, 10)}...${h.substring(h.length - 8)}`;
  };

  return (
    <div className="bg-white border border-[#EAECF0] rounded-xl p-3.5 space-y-2.5 shadow-2xs">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <ShieldCheck className={`w-4 h-4 ${isVerified ? 'text-emerald-600' : 'text-amber-500'}`} />
          <span className="text-xs font-semibold text-text-primary">Крипто-аудит (Merkle)</span>
        </div>
        <span
          className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold border ${
            isVerified
              ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
              : 'bg-amber-50 text-amber-700 border-amber-200'
          }`}
        >
          {isVerified ? 'Верифицировано' : 'Не подтверждено'}
        </span>
      </div>

      {/* Merkle Root Box */}
      <div className="bg-slate-50 border border-slate-200 rounded-lg p-2 font-mono text-[11px] text-slate-700 flex items-center justify-between">
        <div className="truncate mr-2">
          <span className="text-slate-400 select-none mr-1">Root:</span>
          <span className="font-semibold text-slate-800" title={rootHash}>
            {shortHash(rootHash)}
          </span>
        </div>
        <button
          onClick={handleCopyHash}
          disabled={!rootHash}
          className="p-1 text-slate-500 hover:text-slate-800 rounded transition-colors shrink-0 disabled:opacity-40"
          title="Скопировать Merkle Root"
        >
          {copied ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
        </button>
      </div>

      <div className="flex items-center justify-between pt-0.5">
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-[11px] text-[#0EA5E9] hover:text-[#0284C7] font-medium flex items-center gap-1 transition-colors cursor-pointer"
        >
          <span>{expanded ? 'Скрыть детали' : 'Подробнее о хешах'}</span>
          {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
        </button>

        <button
          onClick={handleDownloadCert}
          className="text-[11px] text-slate-600 hover:text-slate-900 font-medium flex items-center gap-1 transition-colors cursor-pointer"
          title="Скачать сертификат достоверности"
        >
          <Download className="w-3 h-3" />
          <span>Сертификат</span>
        </button>
      </div>

      {expanded && (
        <div className="pt-2 border-t border-slate-100 space-y-1.5 text-[10px] font-mono">
          <div className="flex items-center justify-between text-slate-600">
            <span className="flex items-center gap-1 text-slate-500">
              <Hash className="w-3 h-3" /> Входные данные:
            </span>
            <span title={inputsHash} className="font-semibold text-slate-700">
              {shortHash(inputsHash)}
            </span>
          </div>
          <div className="flex items-center justify-between text-slate-600">
            <span className="flex items-center gap-1 text-slate-500">
              <Hash className="w-3 h-3" /> Параметры (Оцу/MMU):
            </span>
            <span title={paramsHash} className="font-semibold text-slate-700">
              {shortHash(paramsHash)}
            </span>
          </div>
          <div className="flex items-center justify-between text-slate-600">
            <span className="flex items-center gap-1 text-slate-500">
              <Hash className="w-3 h-3" /> Итоговые маски:
            </span>
            <span title={resultsHash} className="font-semibold text-slate-700">
              {shortHash(resultsHash)}
            </span>
          </div>
          {sigHash && (
            <div className="flex items-center justify-between text-slate-600">
              <span className="flex items-center gap-1 text-slate-500">
                <FileCode2 className="w-3 h-3" /> Подпись (SHA-256):
              </span>
              <span title={sigHash} className="font-semibold text-slate-700">
                {shortHash(sigHash)}
              </span>
            </div>
          )}
          <div className="text-[9px] text-slate-400 font-sans pt-1 flex items-center justify-between">
            <span className="truncate mr-2">ID: {audit.certificate_id}</span>
            <span>{issuedDate ? new Date(issuedDate).toLocaleDateString('ru-RU') : ''}</span>
          </div>
        </div>
      )}
    </div>
  );
};
