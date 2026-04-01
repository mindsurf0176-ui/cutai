import { useReducer, useEffect, useCallback, useState } from 'react';
import { Settings, Clapperboard, AlertCircle, X } from 'lucide-react';
import { AppContext, appReducer, initialState, useApp } from './store';
import type { AppState } from './store';
import { canAutoStartBackend, healthCheck, startBackend } from './api';
import { initializeAppState, persistPreviewResolution } from './previewResolutionStorage';
import {
  initializeRecentOutputHistoryState,
  persistRecentOutputs,
} from './recentOutputHistoryStorage';
import { initializeRenderPresetState, persistRenderPreset } from './renderPresetStorage';
import {
  initializeSubtitleExportModeState,
  persistSubtitleExportMode,
} from './subtitleExportModeStorage';
import Sidebar from './components/Sidebar';
import BackendGate from './components/BackendGate';
import DropZone from './components/DropZone';
import VideoPreview from './components/VideoPreview';
import EditPlanPanel from './components/EditPlanPanel';
import StylePanel from './components/StylePanel';
import HighlightsPanel from './components/HighlightsPanel';
import InstructionBar from './components/InstructionBar';
import JobProgress from './components/JobProgress';

interface AppMainContentProps {
  onRetryBackend: () => void;
  retryingBackend: boolean;
}

export function AppMainContent({ onRetryBackend, retryingBackend }: AppMainContentProps) {
  const { state } = useApp();

  if (state.backendStatus !== 'online') {
    return (
      <BackendGate
        status={state.backendStatus}
        error={state.backendError}
        onRetry={onRetryBackend}
        retrying={retryingBackend}
      />
    );
  }

  if (state.view === 'upload') {
    return <DropZone />;
  }

  return (
    <div className="flex flex-1 h-full min-h-0">
      <div className="flex-1 flex flex-col p-4 min-w-0 bg-zinc-950/30">
        <VideoPreview />
      </div>

      {state.sidebarTab === 'edit' && state.editPlan && (
        <div className="w-72 border-l border-zinc-800 bg-black flex flex-col z-10">
          <EditPlanPanel />
        </div>
      )}
      {state.sidebarTab === 'style' && (
        <div className="w-72 border-l border-zinc-800 bg-black flex flex-col z-10">
          <StylePanel />
        </div>
      )}
      {state.sidebarTab === 'highlights' && (
        <div className="w-72 border-l border-zinc-800 bg-black flex flex-col z-10">
          <HighlightsPanel />
        </div>
      )}
    </div>
  );
}

export default function App() {
  const [state, dispatch] = useReducer(
    appReducer,
    initialState,
    (baseState: AppState) =>
      initializeSubtitleExportModeState(
        initializeRenderPresetState(
          initializeRecentOutputHistoryState(
            initializeAppState(
              baseState,
              typeof window === 'undefined' ? undefined : window.localStorage
            ),
            typeof window === 'undefined' ? undefined : window.localStorage
          ),
          typeof window === 'undefined' ? undefined : window.localStorage
        ),
        typeof window === 'undefined' ? undefined : window.localStorage
      )
  );
  const [retryingBackend, setRetryingBackend] = useState(false);

  const markBackendOnline = useCallback(() => {
    dispatch({ type: 'SET_BACKEND_STATE', status: 'online', error: null });
  }, []);

  const markBackendOffline = useCallback((error: string) => {
    dispatch({ type: 'SET_BACKEND_STATE', status: 'offline', error });
  }, []);

  const bootstrapBackend = useCallback(async () => {
    dispatch({ type: 'SET_BACKEND_STATE', status: 'checking', error: null });

    const online = await healthCheck();
    if (online) {
      markBackendOnline();
      return;
    }

    if (!canAutoStartBackend()) {
      markBackendOffline(
        'Auis only available in the Tauri desktop app. In browser dev mode, start `cutai server --host 127.0.0.1 --port 18910` manually.'
      );
      return;
    }

    dispatch({ type: 'SET_BACKEND_STATE', status: 'starting', error: null });

    try {
      await startBackend();
      markBackendOnline();
    } catch (error) {
      const message =
        error instanceof Error ? error.message : 'Failed to start the CutAI backend.';
      markBackendOffline(message);
    }
  }, [markBackendOffline, markBackendOnline]);

  const retryBackend = useCallback(async () => {
    setRetryingBackend(true);
    try {
      await bootstrapBackend();
    } finally {
      setRetryingBackend(false);
    }
  }, [bootstrapBackend]);

  useEffect(() => {
    void bootstrapBackend();
  }, [bootstrapBackend]);

  useEffect(() => {
    const interval = setInterval(async () => {
      const online = await healthCheck();

      if (online) {
        markBackendOnline();
        return;
      }

      if (state.backendOnline) {
        markBackendOffline('Lost connection to the local backend. Retry to launch it again.');
      }
    }, 10000);

    return () => clearInterval(interval);
  }, [markBackendOffline, markBackendOnline, state.backendOnline]);

  useEffect(() => {
    persistPreviewResolution(
      typeof window === 'undefined' ? undefined : window.localStorage,
      state.previewResolution
    );
  }, [state.previewResolution]);

  useEffect(() => {
    persistRenderPreset(
      typeof window === 'undefined' ? undefined : window.localStorage,
      state.renderPreset
    );
  }, [state.renderPreset]);

  useEffect(() => {
    persistSubtitleExportMode(
      typeof window === 'undefined' ? undefined : window.localStorage,
      state.subtitleExportMode
    );
  }, [state.subtitleExportMode]);

  useEffect(() => {
    persistRecentOutputs(
      typeof window === 'undefined' ? undefined : window.localStorage,
      state.recentOutputs
    );
  }, [state.recentOutputs]);

  return (
    <AppContext.Provider value={{ state, dispatch }}>
      <div className="flex flex-col h-screen w-screen bg-[#000000]">
        <header className="flex items-center justify-between px-4 h-12 bg-black border-b border-zinc-800 flex-shrink-0 z-50">
          <div className="flex items-center gap-2">
            <Clapperboard size={18} className="text-[#ffffff]" />
            <span className="text-sm font-semibold tracking-tight">CutAI</span>
          </div>
          <button className="p-2 rounded-lg hover:bg-[#18181b] transition-colors">
            <Settings size={16} className="text-[#a1a1aa]" />
          </button>
        </header>

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

        <div className="flex flex-1 min-h-0">
          <Sidebar />
          <main className="flex-1 flex flex-col min-h-0">
            <AppMainContent
              onRetryBackend={retryBackend}
              retryingBackend={retryingBackend}
            />
          </main>
        </div>

        <InstructionBar />
        <JobProgress />
      </div>
    </AppContext.Provider>
  );
}
