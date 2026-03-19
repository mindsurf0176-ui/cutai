import {
  Scissors,
  Subtitles,
  Music,
  Palette,
  ArrowRightLeft,
  Gauge,
  Trash2,
  Play,
  Download,
} from 'lucide-react';
import { useApp } from '../store';
import { startRender } from '../api';

const OPERATION_ICONS: Record<string, typeof Scissors> = {
  cut: Scissors,
  subtitle: Subtitles,
  bgm: Music,
  colorgrade: Palette,
  transition: ArrowRightLeft,
  speed: Gauge,
};

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

export default function EditPlanPanel() {
  const { state, dispatch } = useApp();
  const { editPlan, videoId } = state;

  if (!editPlan) return null;

  const handleRender = async () => {
    if (!videoId || !editPlan) return;
    try {
      const { job_id } = await startRender(videoId, editPlan);
      dispatch({
        type: 'SET_ACTIVE_JOB',
        job: { job_id, status: 'running', progress: 0 },
      });
      dispatch({ type: 'SET_VIEW', view: 'rendering' });
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to start render';
      dispatch({ type: 'SET_ERROR', error: msg });
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--bg-tertiary)]">
        <h3 className="text-sm font-medium">Edit Plan</h3>
        <button
          onClick={() => dispatch({ type: 'CLEAR_EDIT_PLAN' })}
          className="text-xs text-[var(--text-secondary)] hover:text-[var(--error)] transition-colors"
        >
          Clear
        </button>
      </div>

      {/* Summary */}
      <div className="px-4 py-3 text-xs text-[var(--text-secondary)] border-b border-[var(--bg-tertiary)]">
        <p className="italic">"{editPlan.instruction}"</p>
        <p className="mt-1">
          Estimated output: {formatTime(editPlan.estimated_duration)}
        </p>
      </div>

      {/* Operations list */}
      <div className="flex-1 overflow-y-auto">
        {editPlan.operations.map((op, index) => {
          const Icon = OPERATION_ICONS[op.type] ?? Scissors;
          return (
            <div
              key={index}
              className="flex items-center gap-3 px-4 py-3 border-b border-[var(--bg-tertiary)]/50 group hover:bg-[var(--bg-tertiary)]/30 transition-colors"
            >
              <div className="w-7 h-7 rounded-md bg-[var(--accent)]/10 flex items-center justify-center flex-shrink-0">
                <Icon size={14} className="text-[var(--accent)]" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium capitalize">{op.type}</p>
                {op.description && (
                  <p className="text-[11px] text-[var(--text-secondary)] truncate">
                    {op.description}
                  </p>
                )}
                {op.start_time !== undefined && op.end_time !== undefined && (
                  <p className="text-[10px] text-[var(--text-secondary)] tabular-nums">
                    {formatTime(op.start_time)} → {formatTime(op.end_time)}
                  </p>
                )}
              </div>
              <button
                onClick={() => dispatch({ type: 'REMOVE_OPERATION', index })}
                className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-[var(--error)]/20 transition-all"
              >
                <Trash2 size={12} className="text-[var(--error)]" />
              </button>
            </div>
          );
        })}
        {editPlan.operations.length === 0 && (
          <div className="flex items-center justify-center h-20 text-xs text-[var(--text-secondary)]">
            No operations — add instructions below
          </div>
        )}
      </div>

      {/* Action buttons */}
      <div className="flex gap-2 px-4 py-3 border-t border-[var(--bg-tertiary)]">
        <button
          onClick={handleRender}
          disabled={editPlan.operations.length === 0}
          className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg
            bg-[var(--accent)] text-white text-sm font-medium
            hover:bg-[var(--accent-hover)]
            disabled:opacity-40 disabled:cursor-not-allowed
            transition-colors"
        >
          <Download size={14} />
          Render
        </button>
        <button
          disabled={editPlan.operations.length === 0}
          className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg
            bg-[var(--bg-tertiary)] text-[var(--text-secondary)] text-sm
            hover:bg-[var(--bg-tertiary)]/80
            disabled:opacity-40 disabled:cursor-not-allowed
            transition-colors"
        >
          <Play size={14} />
          Preview
        </button>
      </div>
    </div>
  );
}
