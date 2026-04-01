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
    <aside className="w-[68px] flex flex-col items-center bg-[#12121A]/80 backdrop-blur-2xl border border-white/10 rounded-2xl py-4 z-20 flex-shrink-0 shadow-2xl ring-1 ring-white/5">
      <div className="w-11 h-11 flex items-center justify-center rounded-[14px] bg-gradient-to-br from-violet-500 via-purple-500 to-fuchsia-500 text-white mb-6 shadow-[0_4px_20px_rgba(168,85,247,0.4)]">
        <Clapperboard size={20} />
      </div>

      <nav className="flex flex-col gap-4 w-full px-2">
        {TABS.map(({ id, label, icon: Icon }) => {
          const isActive = state.sidebarTab === id;
          const isDisabled = id !== 'upload' && !state.videoId;

          return (
            <Button
              key={id}
              variant={isActive ? "secondary" : "ghost"}
              size="icon"
              className={`w-full h-12 rounded-xl transition-all duration-200 ${isActive ? 'bg-white/10 text-white shadow-sm' : 'text-muted-foreground hover:bg-white/5 hover:text-foreground'}`}
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

      <Button variant="ghost" size="icon" className="w-12 h-12 rounded-xl text-muted-foreground hover:bg-white/5 hover:text-foreground mb-4">
        <Settings size={22} />
      </Button>
      
      <div className={`w-2 h-2 rounded-full mb-2 ${backendDotClass}`} title={`Backend ${backendLabel}`} />
    </aside>
  );
}
