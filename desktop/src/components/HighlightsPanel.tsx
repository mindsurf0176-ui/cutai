import { useMemo, useState } from 'react';
import { Sparkles, Loader2 } from 'lucide-react';
import { useApp } from '../store';
import { generateHighlights } from '../api';

const DEFAULT_STYLE = 'viral';
const STYLE_OPTIONS = [
  { value: 'viral', label: 'Viral' },
  { value: 'narrative', label: 'Narrative' },
  { value: 'balanced', label: 'Balanced' },
];

export default function HighlightsPanel() {
  const { state, dispatch } = useApp();
  const [targetMinutes, setTargetMinutes] = useState(1);
  const [style, setStyle] = useState(DEFAULT_STYLE);
  const [loading, setLoading] = useState(false);

  const maxMinutes = useMemo(() => {
    const duration = state.analysis?.duration ?? state.videoInfo?.duration ?? 0;
    return Math.max(1, Math.ceil(duration / 60));
  }, [state.analysis?.duration, state.videoInfo?.duration]);

  const handleGenerate = async () => {
    if (!state.videoId) return;

    setLoading(true);
    dispatch({ type: 'SET_ERROR', error: null });

    try {
      const { job_id } = await generateHighlights(state.videoId, targetMinutes * 60, style);
      dispatch({
        type: 'SET_ACTIVE_JOB',
        job: { job_id, type: 'highlights', status: 'running', progress: 0 },
      });
      dispatch({ type: 'SET_VIEW', view: 'editor' });
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to generate highlights';
      dispatch({ type: 'SET_ERROR', error: msg });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full">
      <div className="px-4 py-3 border-b border-[var(--bg-tertiary)]">
        <h3 className="text-sm font-medium flex items-center gap-2">
          <Sparkles size={14} />
          Highlights
        </h3>
        <p className="mt-1 text-xs text-[var(--text-secondary)]">
          Generate a shorter cut from the most engaging scenes.
        </p>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        <label className="block space-y-2">
          <span className="text-xs font-medium text-[var(--text-primary)]">Target length</span>
          <input
            type="range"
            min={1}
            max={maxMinutes}
            step={1}
            value={targetMinutes}
            onChange={(e) => setTargetMinutes(Number(e.target.value))}
            className="w-full accent-[var(--accent)]"
          />
          <div className="flex items-center justify-between text-[11px] text-[var(--text-secondary)]">
            <span>1 min</span>
            <span>{targetMinutes} min target</span>
            <span>{maxMinutes} min max</span>
          </div>
        </label>

        <label className="block space-y-2">
          <span className="text-xs font-medium text-[var(--text-primary)]">Highlight style</span>
          <select
            value={style}
            onChange={(e) => setStyle(e.target.value)}
            className="w-full rounded-lg border border-[var(--bg-tertiary)] bg-[var(--bg-primary)] px-3 py-2 text-sm text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent)]"
          >
            {STYLE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        <div className="rounded-lg border border-[var(--bg-tertiary)] bg-[var(--bg-tertiary)]/30 p-3 text-xs text-[var(--text-secondary)] leading-relaxed">
          CutAI will score scenes, build a highlight plan, and send it back to the Edit tab for review before rendering.
        </div>
      </div>

      <div className="px-4 py-3 border-t border-[var(--bg-tertiary)]">
        <button
          onClick={handleGenerate}
          disabled={!state.videoId || loading}
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-[var(--accent)] text-white text-sm font-medium hover:bg-[var(--accent-hover)] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
          Generate highlights
        </button>
      </div>
    </div>
  );
}
