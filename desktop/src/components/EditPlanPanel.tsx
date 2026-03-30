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
import { startPreview, startRender } from '../api';
import {
  PREVIEW_RESOLUTIONS,
  RENDER_PRESET_OPTIONS,
  SUBTITLE_EXPORT_MODE_OPTIONS,
} from '../types';

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
  const {
    editPlan,
    videoId,
    analysis,
    activeJob,
    previewResult,
    previewResolution,
    renderPreset,
    subtitleExportMode,
  } = state;

  if (!editPlan) return null;

  const previewBusy = activeJob?.type === 'preview' && activeJob.status !== 'failed' && activeJob.status !== 'completed';
  const renderBusy = activeJob?.type === 'render' && activeJob.status !== 'failed' && activeJob.status !== 'completed';
  const canPreview = Boolean(videoId && analysis && !previewBusy);
  const canRender = Boolean(videoId && analysis && editPlan.operations.length > 0 && !renderBusy);
  const hasSubtitleOperation = editPlan.operations.some((operation) => operation.type === 'subtitle');
  const selectedRenderPreset = RENDER_PRESET_OPTIONS.find((preset) => preset.value === renderPreset)
    ?? RENDER_PRESET_OPTIONS[1];
  const selectedSubtitleExportMode = SUBTITLE_EXPORT_MODE_OPTIONS.find(
    (option) => option.value === subtitleExportMode
  ) ?? SUBTITLE_EXPORT_MODE_OPTIONS[0];

  const validationMessage = !videoId
    ? 'Upload a video first.'
    : !analysis
      ? 'Preview and render unlock after analysis completes.'
      : editPlan.operations.length === 0
        ? 'This plan has no edit operations yet.'
        : null;

  const handleRender = async () => {
    if (!videoId || !editPlan || !analysis || renderBusy) return;
    try {
      const { job_id } = await startRender(videoId, editPlan, renderPreset, subtitleExportMode);
      dispatch({ type: 'SET_RENDER_RESULT', render: null });
      dispatch({
        type: 'SET_ACTIVE_JOB',
        job: { job_id, type: 'render', status: 'running', progress: 0 },
      });
      dispatch({ type: 'SET_VIEW', view: 'rendering' });
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to start render';
      dispatch({ type: 'SET_ERROR', error: msg });
    }
  };

  const handlePreview = async () => {
    if (!videoId || !editPlan || !analysis || previewBusy) return;
    try {
      const { job_id } = await startPreview(videoId, editPlan, previewResolution);
      dispatch({ type: 'SET_PREVIEW_RESULT', preview: null });
      dispatch({
        type: 'SET_ACTIVE_JOB',
        job: { job_id, type: 'preview', status: 'running', progress: 0 },
      });
      dispatch({ type: 'SET_VIEW', view: 'editor' });
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to start preview';
      dispatch({ type: 'SET_ERROR', error: msg });
    }
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--bg-tertiary)]">
        <h3 className="text-sm font-medium">Edit Plan</h3>
        <button
          onClick={() => dispatch({ type: 'CLEAR_EDIT_PLAN' })}
          className="text-xs text-[var(--text-secondary)] hover:text-[var(--error)] transition-colors"
        >
          Clear
        </button>
      </div>

      <div className="px-4 py-3 text-xs text-[var(--text-secondary)] border-b border-[var(--bg-tertiary)]">
        <p className="italic">"{editPlan.instruction}"</p>
        <p className="mt-1">
          Estimated output: {formatTime(editPlan.estimated_duration)}
        </p>
      </div>

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

      <div className="border-t border-[var(--bg-tertiary)] px-4 py-3">
        <div className="mb-3 flex items-center justify-between gap-3">
          <div>
            <p className="text-xs font-medium text-[var(--text-primary)]">Preview quality</p>
            <p className="text-[11px] text-[var(--text-secondary)]">
              Lower resolutions generate faster.
            </p>
          </div>
          <div className="inline-flex rounded-lg border border-[var(--bg-tertiary)] bg-[var(--bg-primary)] p-1">
            {PREVIEW_RESOLUTIONS.map((resolution) => {
              const selected = previewResolution === resolution;

              return (
                <button
                  key={resolution}
                  type="button"
                  onClick={() => dispatch({ type: 'SET_PREVIEW_RESOLUTION', resolution })}
                  disabled={previewBusy}
                  className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
                    selected
                      ? 'bg-[var(--accent)] text-white'
                      : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                  } disabled:cursor-not-allowed disabled:opacity-50`}
                >
                  {resolution}p
                </button>
              );
            })}
          </div>
        </div>

        <div className="mb-3">
          <div className="mb-2 flex items-center justify-between gap-3">
            <div>
              <p className="text-xs font-medium text-[var(--text-primary)]">Render quality</p>
              <p className="text-[11px] text-[var(--text-secondary)]">
                {selectedRenderPreset.description}
              </p>
            </div>
            <div className="inline-flex rounded-lg border border-[var(--bg-tertiary)] bg-[var(--bg-primary)] p-1">
              {RENDER_PRESET_OPTIONS.map((preset) => {
                const selected = renderPreset === preset.value;

                return (
                  <button
                    key={preset.value}
                    type="button"
                    onClick={() => dispatch({ type: 'SET_RENDER_PRESET', renderPreset: preset.value })}
                    disabled={renderBusy}
                    className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
                      selected
                        ? 'bg-[var(--accent)] text-white'
                        : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                    } disabled:cursor-not-allowed disabled:opacity-50`}
                  >
                    {preset.label}
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {hasSubtitleOperation && (
          <div className="mb-3">
            <div className="mb-2 flex items-center justify-between gap-3">
              <div>
                <p className="text-xs font-medium text-[var(--text-primary)]">Subtitle export</p>
                <p className="text-[11px] text-[var(--text-secondary)]">
                  {selectedSubtitleExportMode.description}
                </p>
              </div>
            </div>
            <div className="grid grid-cols-1 gap-2">
              {SUBTITLE_EXPORT_MODE_OPTIONS.map((option) => {
                const selected = subtitleExportMode === option.value;

                return (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => dispatch({
                      type: 'SET_SUBTITLE_EXPORT_MODE',
                      subtitleExportMode: option.value,
                    })}
                    disabled={renderBusy}
                    className={`rounded-lg border px-3 py-2 text-left transition-colors ${
                      selected
                        ? 'border-[var(--accent)] bg-[var(--accent)]/10'
                        : 'border-[var(--bg-tertiary)] bg-[var(--bg-primary)] hover:border-[var(--accent)]/40'
                    } disabled:cursor-not-allowed disabled:opacity-50`}
                  >
                    <p className="text-xs font-medium text-[var(--text-primary)]">{option.label}</p>
                    <p className="mt-0.5 text-[11px] text-[var(--text-secondary)]">
                      {option.description}
                    </p>
                  </button>
                );
              })}
            </div>
          </div>
        )}

        <div className="flex gap-2">
          <button
            onClick={handlePreview}
            disabled={!canPreview}
            title={!canPreview ? validationMessage ?? 'Preview is already running' : undefined}
            className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg
              bg-[var(--bg-tertiary)] text-[var(--text-primary)] text-sm font-medium
              hover:bg-[var(--bg-tertiary)]/80
              disabled:opacity-40 disabled:cursor-not-allowed
              transition-colors"
          >
            <Play size={14} />
            {previewBusy
              ? `Previewing ${previewResolution}p`
              : previewResult
                ? `Refresh ${previewResolution}p`
                : `Preview ${previewResolution}p`}
          </button>
          <button
            onClick={handleRender}
            disabled={!canRender}
            title={!canRender ? validationMessage ?? 'Render is already running' : undefined}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg
              bg-[var(--accent)] text-white text-sm font-medium
              hover:bg-[var(--accent-hover)]
              disabled:opacity-40 disabled:cursor-not-allowed
              transition-colors"
          >
            <Download size={14} />
            {renderBusy ? `Rendering ${selectedRenderPreset.label}` : `Render ${selectedRenderPreset.label}`}
          </button>
        </div>
      </div>
      {validationMessage && (
        <div className="px-4 pb-3 text-[11px] text-[var(--text-secondary)]">
          {validationMessage}
        </div>
      )}
    </div>
  );
}
