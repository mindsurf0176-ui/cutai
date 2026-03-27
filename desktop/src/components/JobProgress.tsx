import { useEffect, useRef } from 'react';
import { Loader2, CheckCircle, XCircle, X } from 'lucide-react';
import * as Progress from '@radix-ui/react-progress';
import { useApp } from '../store';
import { connectProgressWs, pollJob, getAnalysis } from '../api';

export default function JobProgress() {
  const { state, dispatch } = useApp();
  const { activeJob } = state;
  const wsRef = useRef<WebSocket | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!activeJob || activeJob.status === 'completed' || activeJob.status === 'failed') {
      return;
    }

    // Try WebSocket first
    const ws = connectProgressWs(
      activeJob.job_id,
      (data) => {
        dispatch({
          type: 'UPDATE_JOB_PROGRESS',
          progress: data.progress,
          status: data.status as 'running' | 'completed' | 'failed',
        });
      },
      () => {
        // WebSocket closed — fall back to polling
        pollRef.current = setInterval(async () => {
          try {
            const job = await pollJob(activeJob.job_id);
            dispatch({
              type: 'UPDATE_JOB_PROGRESS',
              progress: job.progress,
              status: job.status,
            });
            if (job.status === 'completed' || job.status === 'failed') {
              if (pollRef.current) clearInterval(pollRef.current);
            }
          } catch {
            // ignore poll errors
          }
        }, 2000);
      }
    );

    wsRef.current = ws;

    return () => {
      ws.close();
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [activeJob?.job_id, activeJob?.status, dispatch]);

  // Auto-dismiss completed jobs
  useEffect(() => {
    if (activeJob?.status === 'completed') {
      let isSubscribed = true;

      const handleCompletion = async () => {
        if (activeJob.type === 'analysis' && state.videoId) {
          try {
            const analysisData = activeJob.result || await getAnalysis(state.videoId);
            if (isSubscribed) {
              dispatch({ type: 'SET_ANALYSIS', analysis: analysisData as any });
            }
          } catch (e) {
            console.error('Failed to load analysis:', e);
          }
        }

        if (isSubscribed) {
          setTimeout(() => {
            if (isSubscribed) {
              dispatch({ type: 'CLEAR_JOB' });
              if (state.view === 'rendering') {
                dispatch({ type: 'SET_VIEW', view: 'editor' });
              }
            }
          }, 3000);
        }
      };

      handleCompletion();

      return () => {
        isSubscribed = false;
      };
    }
  }, [activeJob?.status, activeJob?.type, activeJob?.result, state.videoId, state.view, dispatch]);

  if (!activeJob) return null;

  const statusText = {
    pending: 'Preparing...',
    running: activeJob.progress > 0 ? `Processing... ${activeJob.progress}%` : 'Processing...',
    completed: 'Done!',
    failed: activeJob.error ?? 'Failed',
  }[activeJob.status];

  const StatusIcon = {
    pending: Loader2,
    running: Loader2,
    completed: CheckCircle,
    failed: XCircle,
  }[activeJob.status];

  const statusColor = {
    pending: 'text-[var(--text-secondary)]',
    running: 'text-[var(--accent)]',
    completed: 'text-[var(--success)]',
    failed: 'text-[var(--error)]',
  }[activeJob.status];

  return (
    <div className="fixed bottom-20 right-6 z-50 w-72 bg-[var(--bg-secondary)] border border-[var(--bg-tertiary)] rounded-xl shadow-2xl overflow-hidden animate-in slide-in-from-bottom-4">
      <div className="flex items-center justify-between px-4 py-3">
        <div className="flex items-center gap-2">
          <StatusIcon
            size={16}
            className={`${statusColor} ${activeJob.status === 'running' || activeJob.status === 'pending' ? 'animate-spin' : ''}`}
          />
          <span className="text-sm font-medium">{statusText}</span>
        </div>
        <button
          onClick={() => dispatch({ type: 'CLEAR_JOB' })}
          className="p-1 rounded hover:bg-[var(--bg-tertiary)] transition-colors"
        >
          <X size={14} className="text-[var(--text-secondary)]" />
        </button>
      </div>

      <div className="px-4 pb-3">
        <Progress.Root
          className="relative w-full h-1.5 overflow-hidden rounded-full bg-[var(--bg-primary)]"
          value={activeJob.progress}
        >
          <Progress.Indicator
            className={`h-full rounded-full transition-[width] duration-500 ease-out ${
              activeJob.status === 'completed'
                ? 'bg-[var(--success)]'
                : activeJob.status === 'failed'
                ? 'bg-[var(--error)]'
                : 'bg-[var(--accent)]'
            }`}
            style={{ width: `${activeJob.status === 'completed' ? 100 : activeJob.progress}%` }}
          />
        </Progress.Root>
      </div>
    </div>
  );
}
