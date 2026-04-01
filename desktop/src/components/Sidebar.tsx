import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import {
  Upload,
  Scissors,
  Palette,
  Sparkles,
  Film,
  Clock,
  Maximize,
} from 'lucide-react';
import { useApp, type SidebarTab } from '../store';

const TABS: { id: SidebarTab; label: string; icon: typeof Upload }[] = [
  { id: 'upload', label: 'Upload', icon: Upload },
  { id: 'edit', label: 'Edit', icon: Scissors },
  { id: 'style', label: 'Style', icon: Palette },
  { id: 'highlights', label: 'Highlights', icon: Sparkles },
];

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

export default function Sidebar() {
  const { state, dispatch } = useApp();
  const backendLabel =
    state.backendStatus === 'starting'
      ? 'starting'
      : state.backendStatus === 'checking'
        ? 'checking'
        : state.backendOnline
          ? 'online'
          : 'offline';
  const backendDotClass =
    state.backendStatus === 'starting' || state.backendStatus === 'checking'
      ? 'bg-[var(--warning)]'
      : state.backendOnline
        ? 'bg-[var(--success)]'
        : 'bg-[var(--error)]';

  return (
    <aside className="flex flex-col w-64 bg-black border-r border-[#27272a]/70 h-full">
      {/* Tab navigation */}
      <nav className="flex flex-col gap-1 p-3">
        {TABS.map(({ id, label, icon: Icon }) => {
          const isActive = state.sidebarTab === id;
          const isDisabled = id !== 'upload' && !state.videoId;

          return (
            <button
              key={id}
              onClick={() => {
                if (!isDisabled) {
                  dispatch({ type: 'SET_SIDEBAR_TAB', tab: id });
                  if (id === 'upload') {
                    dispatch({ type: 'SET_VIEW', view: 'upload' });
                  } else {
                    dispatch({ type: 'SET_VIEW', view: 'editor' });
                  }
                }
              }}
              disabled={isDisabled}
              className={`flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-all duration-200 ease-out ${isActive ? 'bg-[#18181b] text-white font-medium shadow-[inset_0_1px_0_0_rgba(255,255,255,0.05)]' : 'text-[#a1a1aa] hover:bg-[#18181b] hover:text-[#fafafa]'}
                ${isDisabled ? 'opacity-30 cursor-not-allowed' : 'cursor-pointer'}
              `}
            >
              <Icon size={16} />
              {label}
            </button>
          );
        })}
      </nav>

      {/* Divider */}
      <div className="mx-3 border-t border-[#27272a]" />

      {/* Project info */}
      {state.videoInfo && (
        <div className="flex flex-col gap-3 p-4 mt-2">
          <h4 className="text-xs font-medium text-[#a1a1aa] uppercase tracking-wider">
            Project
          </h4>

          <div className="flex items-start gap-2">
            <Film size={14} className="text-[#a1a1aa] mt-0.5 flex-shrink-0" />
            <p className="text-xs text-[#fafafa] break-all leading-relaxed">
              {state.videoInfo.original_name}
            </p>
          </div>

          <div className="grid grid-cols-2 gap-2 text-[11px]">
            <div className="flex items-center gap-1.5 text-[#a1a1aa]">
              <Clock size={11} />
              {formatDuration(state.videoInfo.duration)}
            </div>
            <div className="flex items-center gap-1.5 text-[#a1a1aa]">
              <Maximize size={11} />
              {state.videoInfo.width}×{state.videoInfo.height}
            </div>
          </div>

          <p className="text-[10px] text-[#a1a1aa]">
            {state.videoInfo.fps} fps · {formatFileSize(state.videoInfo.file_size)}
          </p>
        </div>
      )}

      {/* Spacer */}
      <div className="flex-1" />

      {/* Backend status */}
      <div className="p-3 border-t border-[#27272a]">
        <div className="flex items-center gap-2 text-[11px] text-[#a1a1aa]">
          <div className={`w-1.5 h-1.5 rounded-md ${backendDotClass}`} />
          Backend {backendLabel}
        </div>
      </div>
    </aside>
  );
}
