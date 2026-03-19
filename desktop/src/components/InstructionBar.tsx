import { useState } from 'react';
import { Send, Scissors, Subtitles, Clapperboard } from 'lucide-react';
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

  const handleSubmit = async (text: string) => {
    if (!state.videoId || !text.trim()) return;
    setLoading(true);
    dispatch({ type: 'SET_ERROR', error: null });

    try {
      const plan = await createPlan(state.videoId, text.trim());
      dispatch({ type: 'SET_EDIT_PLAN', plan });
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
    <div className="border-t border-[var(--bg-tertiary)] bg-[var(--bg-secondary)] px-4 py-3">
      {/* Quick presets */}
      {state.videoId && !state.editPlan && (
        <div className="flex gap-2 mb-3">
          {QUICK_PRESETS.map(({ label, icon: Icon, instruction: preset }) => (
            <button
              key={label}
              onClick={() => handleSubmit(preset)}
              disabled={disabled}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-full
                bg-[var(--bg-tertiary)] text-[var(--text-secondary)]
                hover:bg-[var(--accent)]/20 hover:text-[var(--accent)]
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
        <div className="mb-2 px-3 py-2 rounded-lg bg-[var(--accent)]/10 border border-[var(--accent)]/20 text-xs text-[var(--text-secondary)]">
          <span className="text-[var(--accent)] font-medium">Plan:</span>{' '}
          {state.editPlan.summary}
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
              ? 'Type editing instruction... (e.g., "Cut the first 10 seconds")'
              : 'Upload a video first to start editing'
          }
          disabled={disabled}
          className="flex-1 bg-[var(--bg-primary)] border border-[var(--bg-tertiary)] rounded-lg px-4 py-2.5 text-sm
            text-[var(--text-primary)] placeholder:text-[var(--text-secondary)]/50
            focus:outline-none focus:border-[var(--accent)]
            disabled:opacity-40 disabled:cursor-not-allowed
            transition-colors"
        />
        <button
          type="submit"
          disabled={disabled || !instruction.trim()}
          className="w-10 h-10 rounded-lg bg-[var(--accent)] text-white
            flex items-center justify-center
            hover:bg-[var(--accent-hover)]
            disabled:opacity-40 disabled:cursor-not-allowed
            transition-colors"
        >
          {loading ? (
            <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
          ) : (
            <Send size={16} />
          )}
        </button>
      </form>
    </div>
  );
}
