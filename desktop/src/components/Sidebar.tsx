import {
  Upload,
  Scissors,
  Palette,
  Sparkles,
  Settings,
  Clapperboard
} from 'lucide-react';
import { useApp, type SidebarTab } from '../store';
import { Button } from '@/components/ui/button';

const TABS: { id: SidebarTab; label: string; icon: typeof Upload }[] = [
  { id: 'upload', label: 'Upload', icon: Upload },
  { id: 'edit', label: 'Edit', icon: Scissors },
  { id: 'style', label: 'Style', icon: Palette },
  { id: 'highlights', label: 'Highlights', icon: Sparkles },
];

export default function Sidebar() {
  const { state, dispatch } = useApp();
  const backendLabel = state.backendStatus === 'starting' ? 'starting' : state.backendStatus === 'checking' ? 'checking' : state.backendOnline ? 'online' : 'offline';
  const backendDotClass = state.backendStatus === 'starting' || state.backendStatus === 'checking' ? 'bg-yellow-500' : state.backendOnline ? 'bg-green-500' : 'bg-red-500';

  return (
    <aside className="w-[64px] flex flex-col items-center bg-bg-elevated border border-border py-4 z-20 flex-shrink-0 shadow-lg">
      <div className="w-10 h-10 flex items-center justify-center mb-6 overflow-hidden rounded-lg border border-border">
        <img src="/logo.png" alt="CutAI" className="w-full h-full object-cover" />
      </div>

      <nav className="flex flex-col gap-2 w-full px-3">
        {TABS.map(({ id, label, icon: Icon }) => {
          const isActive = state.sidebarTab === id;
          const isDisabled = id !== 'upload' && !state.videoId;

          return (
            <Button
              key={id}
              variant={isActive ? "secondary" : "ghost"}
              size="icon"
              className={`w-full h-12 rounded-lg transition-colors duration-200 ${isActive ? 'bg-accent text-text-primary' : 'text-text-secondary hover:bg-border hover:text-text-primary'}`}
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
              title={label}
            >
              <Icon size={22} strokeWidth={isActive ? 2.5 : 2} />
            </Button>
          );
        })}
      </nav>

      <div className="flex-1" />

      <Button variant="ghost" size="icon" className="w-12 h-12 rounded-lg text-text-secondary hover:bg-border hover:text-text-primary mb-4">
        <Settings size={22} />
      </Button>
      
      <div className={`w-2 h-2 rounded-full mb-3 ${backendDotClass}`} title={`Backend ${backendLabel}`} />
    </aside>
  );
}