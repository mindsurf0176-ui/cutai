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
      <div className="flex-1 rounded-2xl border border-white/5 bg-zinc-950/50 backdrop-blur-xl shadow-2xl flex items-center justify-center">
        <BackendGate
          status={state.backendStatus}
          error={state.backendError}
          onRetry={onRetryBackend}
          retrying={retryingBackend}
        />
      </div>
    );
  }

  return (
    <div className="flex flex-1 h-full min-h-0 gap-4">
      {/* Center Canvas - The Hero Area */}
      <div className="flex-1 flex flex-col relative min-w-0 rounded-2xl border border-white/5 bg-[#0A0A0F] shadow-2xl overflow-hidden ring-1 ring-white/5">
        {/* Top Bar Floating inside canvas */}
        {state.view !== 'upload' && (
          <header className="absolute top-0 left-0 w-full h-16 flex items-center px-6 z-10 bg-gradient-to-b from-black/80 to-transparent">
            <div className="flex items-center gap-2 text-sm text-zinc-400 font-medium">
              {state.videoInfo?.original_name || 'PROJECT CANVAS'}
            </div>
          </header>
        )}

        <div className="flex-1 flex items-center justify-center p-0 m-0 w-full h-full relative">
          {state.view === 'upload' ? <DropZone /> : <VideoPreview />}
        </div>

        {/* Floating Command Bar (Raycast / Linear style) */}
        {state.view !== 'upload' && (
          <div className="absolute bottom-8 left-1/2 -translate-x-1/2 w-full max-w-2xl z-50 transition-all duration-500 ease-out translate-y-0 opacity-100">
            <InstructionBar />
          </div>
        )}
      </div>

      {/* Right Inspector Panel - Floating Card */}
      {(state.sidebarTab === 'edit' || state.sidebarTab === 'style' || state.sidebarTab === 'highlights') && state.view !== 'upload' && (
        <div className="w-[320px] rounded-2xl border border-white/5 bg-[#12121A]/80 backdrop-blur-2xl shadow-2xl z-10 flex flex-col overflow-hidden ring-1 ring-white/5">
          {state.sidebarTab === 'edit' && <EditPlanPanel />}
          {state.sidebarTab === 'style' && <StylePanel />}
          {state.sidebarTab === 'highlights' && <HighlightsPanel />}
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
      {/* Spatial UI Background Wrapper (Arc/Zed style) */}
      <div className="flex h-screen w-screen bg-[#060609] p-3 gap-3 overflow-hidden selection:bg-zinc-800">
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
