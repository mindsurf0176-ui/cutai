import { useEffect, useState } from 'react';
import { Palette, Check, Loader2 } from 'lucide-react';
import { useApp } from '../store';
import { getPresets, applyStyle } from '../api';

export default function StylePanel() {
  const { state, dispatch } = useApp();
  const [applying, setApplying] = useState<string | null>(null);
  const [applied, setApplied] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    if (state.presets.length > 0) return;
    let cancelled = false;

    getPresets()
      .then((presets) => {
        if (!cancelled) dispatch({ type: 'SET_PRESETS', presets });
      })
      .catch((err) => {
        if (!cancelled) setLoadError(err instanceof Error ? err.message : 'Failed to load presets');
      });

    return () => { cancelled = true; };
  }, [dispatch, state.presets.length]);

  const handleApply = async (presetName: string) => {
    if (!state.videoId) return;
    setApplying(presetName);
    setApplied(null);

    try {
      const { job_id } = await applyStyle(state.videoId, presetName);
      dispatch({
        type: 'SET_ACTIVE_JOB',
        job: { job_id, status: 'running', progress: 0 },
      });
      setApplied(presetName);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to apply style';
      dispatch({ type: 'SET_ERROR', error: msg });
    } finally {
      setApplying(null);
    }
  };

  return (
    <div className="flex flex-col h-full">
      <div className="px-4 py-3 border-b border-[var(--bg-tertiary)]">
        <h3 className="text-sm font-medium flex items-center gap-2">
          <Palette size={14} />
          Style Presets
        </h3>
      </div>

      <div className="flex-1 overflow-y-auto p-3">
        {loadError && (
          <div className="text-xs text-[var(--error)] px-3 py-2 rounded bg-[var(--error)]/10 mb-3">
            {loadError}
          </div>
        )}

        {state.presets.length === 0 && !loadError && (
          <div className="flex items-center justify-center h-20 text-xs text-[var(--text-secondary)]">
            <Loader2 size={16} className="animate-spin mr-2" />
            Loading presets...
          </div>
        )}

        <div className="grid gap-2">
          {state.presets.map((preset) => {
            const isApplied = applied === preset.name;
            const isApplying = applying === preset.name;

            return (
              <button
                key={preset.name}
                onClick={() => handleApply(preset.name)}
                disabled={!state.videoId || isApplying}
                className={`
                  flex items-center gap-3 px-3 py-3 rounded-lg text-left
                  transition-all duration-200
                  disabled:opacity-40 disabled:cursor-not-allowed
                  ${isApplied
                    ? 'bg-[var(--accent)]/15 border border-[var(--accent)]/30'
                    : 'bg-[var(--bg-tertiary)]/50 border border-transparent hover:bg-[var(--bg-tertiary)] hover:border-[var(--bg-tertiary)]'
                  }
                `}
              >
                <div className={`
                  w-8 h-8 rounded-md flex items-center justify-center flex-shrink-0
                  ${isApplied ? 'bg-[var(--accent)]' : 'bg-[var(--bg-primary)]'}
                `}>
                  {isApplying ? (
                    <Loader2 size={14} className="animate-spin text-[var(--accent)]" />
                  ) : isApplied ? (
                    <Check size={14} className="text-white" />
                  ) : (
                    <Palette size={14} className="text-[var(--text-secondary)]" />
                  )}
                </div>
                <div className="min-w-0">
                  <p className="text-xs font-medium capitalize">{preset.name}</p>
                  {preset.description && (
                    <p className="text-[11px] text-[var(--text-secondary)] truncate">
                      {preset.description}
                    </p>
                  )}
                </div>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
