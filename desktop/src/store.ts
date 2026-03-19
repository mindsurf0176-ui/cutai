import { createContext, useContext } from 'react';
import type { VideoInfo, VideoAnalysis, EditPlan, Job, Preset } from './types';

export type ViewMode = 'upload' | 'editor' | 'rendering';
export type SidebarTab = 'upload' | 'edit' | 'style' | 'highlights';

export interface AppState {
  videoId: string | null;
  videoInfo: VideoInfo | null;
  analysis: VideoAnalysis | null;
  editPlan: EditPlan | null;
  activeJob: Job | null;
  presets: Preset[];
  view: ViewMode;
  sidebarTab: SidebarTab;
  uploadProgress: number;
  backendOnline: boolean;
  error: string | null;
  currentTime: number;
}

export const initialState: AppState = {
  videoId: null,
  videoInfo: null,
  analysis: null,
  editPlan: null,
  activeJob: null,
  presets: [],
  view: 'upload',
  sidebarTab: 'upload',
  uploadProgress: 0,
  backendOnline: false,
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
  | { type: 'CLEAR_JOB' }
  | { type: 'SET_PRESETS'; presets: Preset[] }
  | { type: 'SET_VIEW'; view: ViewMode }
  | { type: 'SET_SIDEBAR_TAB'; tab: SidebarTab }
  | { type: 'SET_UPLOAD_PROGRESS'; progress: number }
  | { type: 'SET_BACKEND_ONLINE'; online: boolean }
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
        error: null,
      };
    case 'SET_ANALYSIS':
      return { ...state, analysis: action.analysis };
    case 'SET_EDIT_PLAN':
      return { ...state, editPlan: action.plan };
    case 'CLEAR_EDIT_PLAN':
      return { ...state, editPlan: null };
    case 'REMOVE_OPERATION': {
      if (!state.editPlan) return state;
      const operations = state.editPlan.operations.filter((_, i) => i !== action.index);
      return {
        ...state,
        editPlan: { ...state.editPlan, operations },
      };
    }
    case 'SET_ACTIVE_JOB':
      return { ...state, activeJob: action.job };
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
    case 'CLEAR_JOB':
      return { ...state, activeJob: null };
    case 'SET_PRESETS':
      return { ...state, presets: action.presets };
    case 'SET_VIEW':
      return { ...state, view: action.view };
    case 'SET_SIDEBAR_TAB':
      return { ...state, sidebarTab: action.tab };
    case 'SET_UPLOAD_PROGRESS':
      return { ...state, uploadProgress: action.progress };
    case 'SET_BACKEND_ONLINE':
      return { ...state, backendOnline: action.online };
    case 'SET_ERROR':
      return { ...state, error: action.error };
    case 'SET_CURRENT_TIME':
      return { ...state, currentTime: action.time };
    case 'RESET':
      return { ...initialState, backendOnline: state.backendOnline, presets: state.presets };
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
