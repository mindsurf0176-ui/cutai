import { Button } from '@/components/ui/button';
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
      <div className="flex w-full max-w-lg flex-col gap-5 rounded-xl border border-border bg-card px-8 py-7 shadow-[0_24px_80px_rgba(0,0,0,0.35)]">
        <div className="flex items-start gap-4">
          <div className="mt-0.5 rounded-lg bg-background p-3">
            {busy ? (
              <LoaderCircle size={26} className="animate-spin text-foreground" />
            ) : (
              <ServerCrash size={26} className="text-[hsl(var(--destructive))]" />
            )}
          </div>
          <div className="flex-1">
            <h2 className="text-lg font-semibold text-foreground">{copy.title}</h2>
            <p className="mt-1 text-sm leading-6 text-muted-foreground">
              {copy.description}
            </p>
          </div>
        </div>

        {status === 'offline' && error && (
          <div className="flex items-start gap-2 rounded-lg border border-[hsl(var(--destructive))]/20 bg-[hsl(var(--destructive))]/10 px-4 py-3 text-sm text-foreground">
            <AlertCircle size={16} className="mt-0.5 flex-shrink-0 text-[hsl(var(--destructive))]" />
            <span>{error}</span>
          </div>
        )}

        <div className="flex items-center justify-between gap-3 border-t border-border pt-4">
          <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
            Port 18910
          </p>
          <Button
            type="button"
            onClick={onRetry}
            disabled={busy}
            className="gap-2 font-medium"
          >
            <RefreshCw size={15} className={retrying ? 'animate-spin' : ''} />
            Retry
          </Button>
        </div>
      </div>
    </div>
  );
}
