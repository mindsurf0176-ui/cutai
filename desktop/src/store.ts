import { createContext, useContext } from 'react';
import type {
  VideoInfo,
  VideoAnalysis,
  EditPlan,
  Job,
  Preset,
  PreviewResolution,
  RenderPreset,
  SubtitleExportMode,
  PreviewAsset,
  RenderAsset,
  OutputHistoryItem,
} from './types';

export type ViewMode = 'upload' | 'editor' | 'rendering';
export type SidebarTab = 'upload' | 'edit' | 'style' | 'highlights';
export type BackendStatus = 'checking' | 'starting' | 'online' | 'offline';
export const RECENT_OUTPUT_HISTORY_LIMIT = 12;

function mergeRecentOutputs(
  recentOutputs: OutputHistoryItem[],
  item: OutputHistoryItem
): OutputHistoryItem[] {
  return [item, ...recentOutputs.filter((entry) => (
    !(entry.kind === item.kind && entry.job_id === item.job_id)
  ))].slice(0, RECENT_OUTPUT_HISTORY_LIMIT);
}

export interface AppState {
  videoId: string | null;
  videoInfo: VideoInfo | null;
  analysis: VideoAnalysis | null;
  editPlan: EditPlan | null;
  activeJob: Job | null;
  previewResult: PreviewAsset | null;
  previewResolution: PreviewResolution;
  renderPreset: RenderPreset;
  subtitleExportMode: SubtitleExportMode;
  renderResult: RenderAsset | null;
  recentOutputs: OutputHistoryItem[];
  presets: Preset[];
  planningStylePreset: Preset | null;
  view: ViewMode;
  sidebarTab: SidebarTab;
  uploadProgress: number;
  backendStatus: BackendStatus;
  backendOnline: boolean;
  backendError: string | null;
  error: string | null;
  currentTime: number;
}

export const initialState: AppState = {
  videoId: null,
  videoInfo: null,
  analysis: null,
  editPlan: null,
  activeJob: null,
  previewResult: null,
  previewResolution: 360,
  renderPreset: 'balanced',
  subtitleExportMode: 'burned',
  renderResult: null,
  recentOutputs: [],
  presets: [],
  planningStylePreset: null,
  view: 'upload',
  sidebarTab: 'upload',
  uploadProgress: 0,
  backendStatus: 'checking',
  backendOnline: false,
  backendError: null,
  error: null,
  currentTime: 0,
};

export type AppAction =
  | { type: 'SET_VIDEO'; videoId: string; videoInfo: VideoInfo }
  | { type: 'SET_ANALYSIS'; analysis: VideoAnalysis }
  | { type: 'SET_EDIT_PLAN'; plan: EditPlan }
  | { type: 'CLEAR_EDIT_PLAN' }
  | { type: 'REMOVE_OPERATION'; index: number }
  | { type: 'SET_ACTIVE_JOB'; job: Job }
  | { type: 'UPDATE_JOB_PROGRESS'; progress: number; status: Job['status'] }
  | { type: 'SET_PREVIEW_RESULT'; preview: PreviewAsset | null }
  | { type: 'SET_PREVIEW_RESOLUTION'; resolution: PreviewResolution }
  | { type: 'SET_RENDER_PRESET'; renderPreset: RenderPreset }
  | { type: 'SET_SUBTITLE_EXPORT_MODE'; subtitleExportMode: SubtitleExportMode }
  | { type: 'SET_RENDER_RESULT'; render: RenderAsset | null }
  | { type: 'SET_RECENT_OUTPUTS'; items: OutputHistoryItem[] }
  | { type: 'ADD_RECENT_OUTPUT'; item: OutputHistoryItem }
  | { type: 'CLEAR_JOB' }
  | { type: 'SET_PRESETS'; presets: Preset[] }
  | { type: 'SET_PLANNING_STYLE_PRESET'; preset: Preset | null }
  | { type: 'SET_VIEW'; view: ViewMode }
  | { type: 'SET_SIDEBAR_TAB'; tab: SidebarTab }
  | { type: 'SET_UPLOAD_PROGRESS'; progress: number }
  | { type: 'SET_BACKEND_STATE'; status: BackendStatus; error?: string | null }
  | { type: 'SET_ERROR'; error: string | null }
  | { type: 'SET_CURRENT_TIME'; time: number }
  | { type: 'RESET' };

export function appReducer(state: AppState, action: AppAction): AppState {
  switch (action.type) {
    case 'SET_VIDEO':
      return {
        ...state,
        videoId: action.videoId,
        videoInfo: action.videoInfo,
        view: 'editor',
        sidebarTab: 'edit',
        uploadProgress: 0,
        previewResult: null,
        renderResult: null,
        error: null,
      };
    case 'SET_ANALYSIS':
      return { ...state, analysis: action.analysis };
    case 'SET_EDIT_PLAN':
      return { ...state, editPlan: action.plan, previewResult: null, renderResult: null };
    case 'CLEAR_EDIT_PLAN':
      return { ...state, editPlan: null, previewResult: null, renderResult: null };
    case 'REMOVE_OPERATION': {
      if (!state.editPlan) return state;
      const operations = state.editPlan.operations.filter((_, i) => i !== action.index);
      return {
        ...state,
        editPlan: { ...state.editPlan, operations },
        previewResult: null,
        renderResult: null,
      };
    }
    case 'SET_ACTIVE_JOB':
      return {
        ...state,
        activeJob: {
          ...state.activeJob,
          ...action.job,
          type: action.job.type ?? state.activeJob?.type,
        },
      };
    case 'UPDATE_JOB_PROGRESS':
      if (!state.activeJob) return state;
      return {
        ...state,
        activeJob: {
          ...state.activeJob,
          progress: action.progress,
          status: action.status,
        },
      };
    case 'SET_PREVIEW_RESULT':
      return { ...state, previewResult: action.preview };
    case 'SET_PREVIEW_RESOLUTION':
      return {
        ...state,
        previewResolution: action.resolution,
        previewResult: null,
      };
    case 'SET_RENDER_PRESET':
      return {
        ...state,
        renderPreset: action.renderPreset,
        renderResult: null,
      };
    case 'SET_SUBTITLE_EXPORT_MODE':
      return {
        ...state,
        subtitleExportMode: action.subtitleExportMode,
        renderResult: null,
      };
    case 'SET_RENDER_RESULT':
      return { ...state, renderResult: action.render };
    case 'SET_RECENT_OUTPUTS':
      return { ...state, recentOutputs: action.items.slice(0, RECENT_OUTPUT_HISTORY_LIMIT) };
    case 'ADD_RECENT_OUTPUT':
      return { ...state, recentOutputs: mergeRecentOutputs(state.recentOutputs, action.item) };
    case 'CLEAR_JOB':
      return { ...state, activeJob: null };
    case 'SET_PRESETS':
      return { ...state, presets: action.presets };
    case 'SET_PLANNING_STYLE_PRESET':
      return { ...state, planningStylePreset: action.preset };
    case 'SET_VIEW':
      return { ...state, view: action.view };
    case 'SET_SIDEBAR_TAB':
      return { ...state, sidebarTab: action.tab };
    case 'SET_UPLOAD_PROGRESS':
      return { ...state, uploadProgress: action.progress };
    case 'SET_BACKEND_STATE':
      return {
        ...state,
        backendStatus: action.status,
        backendOnline: action.status === 'online',
        backendError: action.error ?? null,
      };
    case 'SET_ERROR':
      return { ...state, error: action.error };
    case 'SET_CURRENT_TIME':
      return { ...state, currentTime: action.time };
    case 'RESET':
      return {
        ...initialState,
        backendStatus: state.backendStatus,
        backendOnline: state.backendOnline,
        backendError: state.backendError,
        previewResolution: state.previewResolution,
        renderPreset: state.renderPreset,
        subtitleExportMode: state.subtitleExportMode,
        recentOutputs: state.recentOutputs,
        presets: state.presets,
        planningStylePreset: state.planningStylePreset,
      };
    default:
      return state;
  }
}

interface AppContextType {
  state: AppState;
  dispatch: React.Dispatch<AppAction>;
}

export const AppContext = createContext<AppContextType>({
  state: initialState,
  dispatch: () => undefined,
});

export function useApp() {
  return useContext(AppContext);
}
