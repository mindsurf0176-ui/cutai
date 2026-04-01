import { Button } from '@/components/ui/button';
import { useState } from 'react';
import { Send, Scissors, Subtitles, Clapperboard, Wand2, X } from 'lucide-react';
import { useApp } from '../store';
import { createPlan } from '../api';

const QUICK_PRESETS = [
  { label: 'Remove silence', icon: Scissors, instruction: 'Remove all silent parts' },
  { label: 'Add subtitles', icon: Subtitles, instruction: 'Add subtitles to the video' },
  { label: 'Make cinematic', icon: Clapperboard, instruction: 'Apply cinematic color grading and transitions' },
];

export default function InstructionBar() {
  const { state, dispatch } = useApp();
  const [instruction, setInstruction] = useState('');
  const [loading, setLoading] = useState(false);

  const disabled = !state.videoId || loading;
  const selectedStylePreset = state.planningStylePreset;
  const selectedStylePresetId = selectedStylePreset?.file ?? selectedStylePreset?.name ?? null;
  const isRefiningPlan = Boolean(state.editPlan);

  const composeInstruction = (text: string): string => {
    const trimmed = text.trim();
    const existing = state.editPlan?.instruction.trim();

    if (!existing) return trimmed;

    return `${existing}\n\nAdditional refinement: ${trimmed}`;
  };

  const handleSubmit = async (text: string) => {
    if (!state.videoId || !text.trim()) return;
    setLoading(true);
    dispatch({ type: 'SET_ERROR', error: null });

    try {
      const plan = await createPlan(state.videoId, composeInstruction(text), {
        stylePreset: selectedStylePresetId,
      });
      dispatch({ type: 'SET_EDIT_PLAN', plan });
      dispatch({ type: 'SET_SIDEBAR_TAB', tab: 'edit' });
      dispatch({ type: 'SET_VIEW', view: 'editor' });
      setInstruction('');
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to create plan';
      dispatch({ type: 'SET_ERROR', error: msg });
    } finally {
      setLoading(false);
    }
  };

  const handleFormSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    handleSubmit(instruction);
  };

  return (
    <div className="w-full transition-all duration-300 group relative">
      {selectedStylePreset && state.videoId && (
        <div className="mb-3 flex items-start justify-between gap-3 rounded-lg border border-border bg-bg-panel px-3 py-2">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <Wand2 size={12} className="text-text-primary" />
              <span className="text-xs font-medium text-text-secondary">
                Planning with {selectedStylePreset.name}
              </span>
            </div>
            <p className="mt-1 text-[11px] text-text-muted">
              New instructions use this preset as context instead of only applying it immediately.
            </p>
          </div>
          <button
            type="button"
            onClick={() => dispatch({ type: 'SET_PLANNING_STYLE_PRESET', preset: null })}
            className="rounded-md p-1 text-text-muted hover:bg-border hover:text-text-primary transition-colors"
            aria-label="Clear planning style"
          >
            <X size={12} />
          </button>
        </div>
      )}

      {/* Quick presets */}
      {state.videoId && !state.editPlan && (
        <div className="flex gap-2 mb-3">
          {QUICK_PRESETS.map(({ label, icon: Icon, instruction: preset }) => (
            <button
              key={label}
              onClick={() => handleSubmit(preset)}
              disabled={disabled}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-md
                bg-bg-base text-text-muted
                hover:bg-border hover:text-text-primary
                disabled:opacity-40 disabled:cursor-not-allowed
                transition-colors"
            >
              <Icon size={12} />
              {label}
            </button>
          ))}
        </div>
      )}

      {/* Plan summary */}
      {state.editPlan && (
        <div className="mb-2 px-3 py-2 rounded-lg bg-bg-elevated border border-border text-xs text-text-muted">
          <span className="text-text-primary font-medium">Plan:</span>{' '}
          {state.editPlan.summary}
          {selectedStylePreset && (
            <>
              {' '}
              <span className="text-text-primary font-medium">Style context:</span>{' '}
              {selectedStylePreset.name}
            </>
          )}
        </div>
      )}

      {/* Input */}
      <form onSubmit={handleFormSubmit} className="flex items-center gap-2">
        <input
          type="text"
          value={instruction}
          onChange={(e) => setInstruction(e.target.value)}
          placeholder={
            state.videoId
              ? isRefiningPlan
                ? 'Refine the current plan... (e.g., "make the pacing faster and keep subtitles")'
                : 'Type editing instruction... (e.g., "Cut the first 10 seconds")'
              : 'Tell AI what to do with your video...'
          }
          disabled={disabled}
          className="flex-1 bg-transparent border-none px-4 py-3 text-[15px]
            text-text-primary placeholder:text-text-muted
            focus:outline-none
            disabled:opacity-40 disabled:cursor-not-allowed"
        />
        <button
          type="submit"
          disabled={disabled || !instruction.trim()}
          title={isRefiningPlan ? 'Rebuild the plan with this refinement' : 'Go'}
          className="w-9 h-9 rounded-lg bg-accent text-text-primary
            flex items-center justify-center
            hover:bg-accent/90
            disabled:opacity-40 disabled:cursor-not-allowed
            transition-all active:scale-95"
        >
          {loading ? (
            <div className="w-4 h-4 border-2 border-text-muted border-t-text-primary rounded-md animate-spin" />
          ) : (
            <Send size={16} />
          )}
        </button>
      </form>
    </div>
  );
}