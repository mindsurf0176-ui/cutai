import { useReducer, useEffect, useCallback } from 'react';
import { Settings, Clapperboard, AlertCircle, X } from 'lucide-react';
import { AppContext, appReducer, initialState, useApp } from './store';
import { healthCheck } from './api';
import Sidebar from './components/Sidebar';
import DropZone from './components/DropZone';
import VideoPreview from './components/VideoPreview';
import EditPlanPanel from './components/EditPlanPanel';
import StylePanel from './components/StylePanel';
import InstructionBar from './components/InstructionBar';
import JobProgress from './components/JobProgress';

function AppMainContent() {
  const { state } = useApp();

  if (state.view === 'upload') {
    return <DropZone />;
  }

  return (
    <div className="flex flex-1 h-full min-h-0">
      <div className="flex-1 flex flex-col p-4 min-w-0">
        <VideoPreview />
      </div>

      {state.sidebarTab === 'edit' && state.editPlan && (
        <div className="w-72 border-l border-[var(--bg-tertiary)] bg-[var(--bg-secondary)]">
          <EditPlanPanel />
        </div>
      )}
      {state.sidebarTab === 'style' && (
        <div className="w-72 border-l border-[var(--bg-tertiary)] bg-[var(--bg-secondary)]">
          <StylePanel />
        </div>
      )}
    </div>
  );
}

export default function App() {
  const [state, dispatch] = useReducer(appReducer, initialState);

  // Check backend health periodically
  const checkHealth = useCallback(async () => {
    const online = await healthCheck();
    dispatch({ type: 'SET_BACKEND_ONLINE', online });
  }, []);

  useEffect(() => {
    checkHealth();
    const interval = setInterval(checkHealth, 10000);
    return () => clearInterval(interval);
  }, [checkHealth]);

  return (
    <AppContext.Provider value={{ state, dispatch }}>
      <div className="flex flex-col h-screen w-screen bg-[var(--bg-primary)]">
        {/* Header */}
        <header className="flex items-center justify-between px-4 h-12 bg-[var(--bg-secondary)] border-b border-[var(--bg-tertiary)] flex-shrink-0">
          <div className="flex items-center gap-2">
            <Clapperboard size={18} className="text-[var(--accent)]" />
            <span className="text-sm font-semibold tracking-tight">CutAI</span>
          </div>
          <button className="p-2 rounded-lg hover:bg-[var(--bg-tertiary)] transition-colors">
            <Settings size={16} className="text-[var(--text-secondary)]" />
          </button>
        </header>

        {/* Error banner */}
        {state.error && (
          <div className="flex items-center gap-2 px-4 py-2 bg-[var(--error)]/10 border-b border-[var(--error)]/20 text-sm text-[var(--error)]">
            <AlertCircle size={14} />
            <span className="flex-1">{state.error}</span>
            <button
              onClick={() => dispatch({ type: 'SET_ERROR', error: null })}
              className="p-1 rounded hover:bg-[var(--error)]/20 transition-colors"
            >
              <X size={14} />
            </button>
          </div>
        )}

        {/* Main area */}
        <div className="flex flex-1 min-h-0">
          <Sidebar />
          <main className="flex-1 flex flex-col min-h-0">
            <AppMainContent />
          </main>
        </div>

        {/* Instruction bar */}
        <InstructionBar />

        {/* Job progress overlay */}
        <JobProgress />
      </div>
    </AppContext.Provider>
  );
}
