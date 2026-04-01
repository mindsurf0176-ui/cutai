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

  return (
    <div className="flex flex-col flex-1 h-full min-h-0 gap-3">
      {/* Backend offline notice (small banner, doesn\'t block UI) */}
      {state.backendStatus !== 'online' && (
        <div className="flex items-center gap-3 px-5 py-3 border-b border-amber-500/20 bg-amber-500/5 flex-shrink-0">
          <div className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
          <span className="text-sm text-amber-200/80 font-medium flex-1">
            {state.backendStatus === 'checking' ? 'Connecting to backend...' : state.backendStatus === 'starting' ? 'Starting backend...' : 'Backend offline \u2014 start cutai server to enable editing'}
          </span>
          <button onClick={onRetryBackend} disabled={retryingBackend} className="text-xs font-semibold text-amber-400 hover:text-amber-300 transition-colors disabled:opacity-50">
            {retryingBackend ? 'Retrying...' : 'Retry'}
          </button>
        </div>
      )}
      {state.view === 'upload' ? (
        /* ===== UPLOAD STATE: Minimal, action-first (Runway/Descript style) ===== */
        <div className="flex-1 flex flex-col relative bg-[#0A0A0F] overflow-hidden">
          {/* Full-area drop target */}
          <div className="flex-1 flex flex-col items-center justify-center relative">
            <DropZone />
          </div>

          {/* Command bar docked at bottom */}
          <div className="w-full px-6 pb-6 z-50">
            <InstructionBar />
          </div>
        </div>
      ) : (
        /* ===== EDITING STATE: True NLE layout ===== */
        <>
          <div className="flex flex-1 min-h-0 gap-3">
            <div className="flex-1 flex flex-col relative min-w-0 bg-[#0A0A0F] overflow-hidden">
              <header className="absolute top-0 left-0 w-full h-12 flex items-center justify-between px-5 z-10 bg-gradient-to-b from-black/60 to-transparent">
                <span className="text-sm font-semibold text-white/80">{state.videoInfo?.original_name || 'Untitled Project'}</span>
              </header>
              <div className="flex-1 flex items-center justify-center w-full h-full relative">
                <VideoPreview />
              </div>
            </div>

            {(state.sidebarTab === 'edit' || state.sidebarTab === 'style' || state.sidebarTab === 'highlights') && (
              <div className="w-[320px] border-l border-white/[0.06] bg-[#0A0A0F] z-10 flex flex-col overflow-hidden">
                {state.sidebarTab === 'edit' && <EditPlanPanel />}
                {state.sidebarTab === 'style' && <StylePanel />}
                {state.sidebarTab === 'highlights' && <HighlightsPanel />}
              </div>
            )}
          </div>

          <div className="h-[200px] flex-shrink-0 flex flex-col gap-3">
            <div className="w-full flex-shrink-0 z-50">
              <InstructionBar />
            </div>
            <div className="flex-1 border-t border-white/[0.06] bg-[#0A0A0F] overflow-hidden flex items-center justify-center">
              <div className="text-sm text-white/20 font-medium tracking-widest uppercase">Timeline</div>
            </div>
          </div>
        </>
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
      <div className="flex h-screen w-screen bg-[#000000] overflow-hidden selection:bg-violet-500/30">
        {state.error && (
          <div className="absolute top-6 left-1/2 -translate-x-1/2 flex items-center gap-3 px-5 py-2.5 bg-red-500/10 border border-red-500/20 rounded-full text-red-500 text-sm z-50 backdrop-blur-md shadow-2xl">
            <AlertCircle size={14} />
            <span className="font-medium">{state.error}</span>
            <button
              onClick={() => dispatch({ type: 'SET_ERROR', error: null })}
              className="p-1 rounded-full hover:bg-red-500/20 transition-colors ml-2"
            >
              <X size={12} />
            </button>
          </div>
        )}

        <Sidebar />
        <main className="flex-1 flex flex-col min-w-0">
          <AppMainContent
            onRetryBackend={retryBackend}
            retryingBackend={retryingBackend}
          />
        </main>

        <JobProgress />
      </div>
    </AppContext.Provider>
  );
}
