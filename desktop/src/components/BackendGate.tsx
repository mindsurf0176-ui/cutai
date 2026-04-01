import { AlertCircle, LoaderCircle, RefreshCw, ServerCrash } from 'lucide-react';
import type { BackendStatus } from '../store';

interface BackendGateProps {
  status: BackendStatus;
  error: string | null;
  onRetry: () => void;
  retrying: boolean;
}

function getCopy(status: BackendStatus, error: string | null) {
  if (status === 'checking') {
    return {
      title: 'Checking local backend',
      description: 'Looking for the CutAI backend on 127.0.0.1:18910.',
    };
  }

  if (status === 'starting') {
    return {
      title: 'Starting local backend',
      description: 'Launching the embedded CutAI server. This usually takes a few seconds.',
    };
  }

  return {
    title: 'Backend unavailable',
    description: error
      ? 'CutAI could not reach the local backend. Retry after fixing the local server environment.'
      : 'CutAI could not reach the local backend.',
  };
}

export default function BackendGate({
  status,
  error,
  onRetry,
  retrying,
}: BackendGateProps) {
  const copy = getCopy(status, error);
  const busy = status === 'checking' || status === 'starting' || retrying;

  return (
    <div className="flex h-full items-center justify-center p-8">
      <div className="flex w-full max-w-lg flex-col gap-5 rounded-xl border border-[#27272a] bg-[#09090b] px-8 py-7 shadow-[0_24px_80px_rgba(0,0,0,0.35)]">
        <div className="flex items-start gap-4">
          <div className="mt-0.5 rounded-lg bg-[#000000] p-3">
            {busy ? (
              <LoaderCircle size={26} className="animate-spin text-[#ffffff]" />
            ) : (
              <ServerCrash size={26} className="text-[var(--warning)]" />
            )}
          </div>
          <div className="flex-1">
            <h2 className="text-lg font-semibold text-[#fafafa]">{copy.title}</h2>
            <p className="mt-1 text-sm leading-6 text-[#a1a1aa]">
              {copy.description}
            </p>
          </div>
        </div>

        {status === 'offline' && error && (
          <div className="flex items-start gap-2 rounded-lg border border-[var(--warning)]/20 bg-[var(--warning)]/10 px-4 py-3 text-sm text-[#fafafa]">
            <AlertCircle size={16} className="mt-0.5 flex-shrink-0 text-[var(--warning)]" />
            <span>{error}</span>
          </div>
        )}

        <div className="flex items-center justify-between gap-3 border-t border-[#27272a] pt-4">
          <p className="text-xs uppercase tracking-[0.2em] text-[#a1a1aa]">
            Port 18910
          </p>
          <button
            type="button"
            onClick={onRetry}
            disabled={busy}
            className="inline-flex items-center gap-2 rounded-md bg-[#ffffff] px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <RefreshCw size={15} className={retrying ? 'animate-spin' : ''} />
            Retry
          </button>
        </div>
      </div>
    </div>
  );
}
