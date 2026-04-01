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
    <div className="flex flex-col flex-1 h-full min-h-0">
      {/* Backend status bar */}
      {state.backendStatus !== 'online' && (
        <div className="flex items-center gap-3 px-4 py-2 bg-bg-panel border-b border-border flex-shrink-0">
          <div className="w-1.5 h-1.5 rounded-full bg-warning animate-pulse" />
          <span className="text-xs text-text-secondary flex-1">
            {state.backendStatus === 'checking' ? 'Connecting...' : state.backendStatus === 'starting' ? 'Starting...' : 'Backend offline'}
          </span>
          <button onClick={onRetryBackend} disabled={retryingBackend} className="text-xs font-medium text-accent hover:text-accent-hover transition-colors disabled:opacity-50">
            {retryingBackend ? 'Retrying...' : 'Retry'}
          </button>
        </div>
      )}

      {state.view === 'upload' ? (
        /* ===== UPLOAD: Clean full-screen drop zone ===== */
        <div className="flex-1 flex flex-col min-h-0">
          {/* Canvas area - full clickable drop zone */}
          <div className="flex-1 bg-bg-base">
            <DropZone />
          </div>
          {/* Command bar at bottom */}
          <div className="flex-shrink-0 bg-bg-panel border-t border-border">
            <InstructionBar />
          </div>
        </div>
      ) : (
        /* ===== EDITOR: Video + Inspector (top) | Command + Timeline (bottom) ===== */
        <div className="flex-1 flex flex-col min-h-0">
          {/* Top: Preview + Inspector */}
          <div className="flex flex-1 min-h-0">
            {/* Video Canvas */}
            <div className="flex-1 flex flex-col min-w-0 bg-black relative">
              {/* File name bar */}
              <div className="h-10 flex items-center px-4 bg-bg-panel border-b border-border flex-shrink-0">
                <span className="text-xs font-medium text-text-secondary truncate">{state.videoInfo?.original_name || 'Untitled'}</span>
              </div>
              <div className="flex-1 flex items-center justify-center">
                <VideoPreview />
              </div>
            </div>

            {/* Inspector Panel */}
            {(state.sidebarTab === 'edit' || state.sidebarTab === 'style' || state.sidebarTab === 'highlights') && (
              <div className="w-80 flex flex-col bg-bg-panel border-l border-border overflow-hidden">
                {state.sidebarTab === 'edit' && <EditPlanPanel />}
                {state.sidebarTab === 'style' && <StylePanel />}
                {state.sidebarTab === 'highlights' && <HighlightsPanel />}
              </div>
            )}
          </div>

          {/* Bottom: Command Bar + Timeline */}
          <div className="flex-shrink-0 bg-bg-panel border-t border-border">
            <InstructionBar />
          </div>
          <div className="h-32 flex-shrink-0 bg-bg-base border-t border-border flex items-center justify-center">
            <span className="text-xs text-text-muted font-medium tracking-wider uppercase">Timeline</span>
          </div>
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
      <div className="flex h-screen w-screen bg-bg-base overflow-hidden">
        {state.error && (
          <div className="absolute top-3 left-1/2 -translate-x-1/2 flex items-center gap-2 px-4 py-2 bg-error/10 border border-error/20 rounded-lg text-error text-xs z-50">
            <AlertCircle size={12} />
            <span className="font-medium">{state.error}</span>
            <button onClick={() => dispatch({ type: 'SET_ERROR', error: null })} className="p-0.5 rounded hover:bg-error/20 transition-colors ml-1">
              <X size={10} />
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