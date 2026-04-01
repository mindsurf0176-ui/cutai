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
        <div className="mb-3 flex items-start justify-between gap-3 rounded-lg border border-[#ffffff]/25 bg-[#ffffff]/10 px-3 py-2">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <Wand2 size={12} className="text-[#ffffff]" />
              <span className="text-xs font-medium text-zinc-200">
                Planning with {selectedStylePreset.name}
              </span>
            </div>
            <p className="mt-1 text-[11px] text-zinc-500">
              New instructions use this preset as context instead of only applying it immediately.
            </p>
          </div>
          <button
            type="button"
            onClick={() => dispatch({ type: 'SET_PLANNING_STYLE_PRESET', preset: null })}
            className="rounded-md p-1 text-zinc-500 hover:bg-[#ffffff]/10 hover:text-zinc-200 transition-colors"
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
                bg-[#18181b] text-zinc-500
                hover:bg-[#ffffff]/20 hover:text-[#ffffff]
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
        <div className="mb-2 px-3 py-2 rounded-lg bg-[#ffffff]/10 border border-[#ffffff]/20 text-xs text-zinc-500">
          <span className="text-[#ffffff] font-medium">Plan:</span>{' '}
          {state.editPlan.summary}
          {selectedStylePreset && (
            <>
              {' '}
              <span className="text-[#ffffff] font-medium">Style context:</span>{' '}
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
          className="flex-1 bg-[#000000] border border-[#27272a] rounded-lg px-4 py-2.5 text-sm
            text-zinc-200 placeholder:text-zinc-500/50
            focus:outline-none focus:border-[#ffffff]
            disabled:opacity-40 disabled:cursor-not-allowed
            transition-colors"
        />
        <button
          type="submit"
          disabled={disabled || !instruction.trim()}
          title={isRefiningPlan ? 'Rebuild the plan with this refinement' : 'Go'}
          className="w-10 h-10 rounded-lg bg-[#ffffff] text-white
            flex items-center justify-center
            hover:bg-[#e4e4e7]
            disabled:opacity-40 disabled:cursor-not-allowed
            transition-colors"
        >
          {loading ? (
            <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-md animate-spin" />
          ) : (
            <Send size={16} />
          )}
        </button>
      </form>
    </div>
  );
}
