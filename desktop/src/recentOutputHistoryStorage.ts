import type { AppState } from './store';
import { RECENT_OUTPUT_HISTORY_LIMIT } from './store';
import type {
  OutputHistoryItem,
  OutputKind,
  RenderPreset,
  SubtitleExportMode,
} from './types';

export const RECENT_OUTPUT_HISTORY_STORAGE_KEY = 'cutai.desktop.recentOutputs';

interface StorageLike {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

function isOutputKind(value: unknown): value is OutputKind {
  return value === 'preview' || value === 'render';
}

function isRenderPreset(value: unknown): value is RenderPreset {
  return value === 'draft' || value === 'balanced' || value === 'high';
}

function isSubtitleExportMode(value: unknown): value is SubtitleExportMode {
  return value === 'burned' || value === 'sidecar';
}

function isValidHistoryItem(value: unknown): value is OutputHistoryItem {
  if (!value || typeof value !== 'object') {
    return false;
  }

  const item = value as Record<string, unknown>;

  if (
    typeof item.job_id !== 'string'
    || typeof item.output_path !== 'string'
    || !isOutputKind(item.kind)
    || typeof item.completed_at !== 'string'
  ) {
    return false;
  }

  if (item.resolution !== undefined && typeof item.resolution !== 'number') {
    return false;
  }

  if (item.render_preset !== undefined && !isRenderPreset(item.render_preset)) {
    return false;
  }

  if (
    item.subtitle_export_mode !== undefined
    && !isSubtitleExportMode(item.subtitle_export_mode)
  ) {
    return false;
  }

  if (item.subtitle_path !== undefined && typeof item.subtitle_path !== 'string') {
    return false;
  }

  return true;
}

export function loadStoredRecentOutputs(
  storage: Pick<StorageLike, 'getItem'> | undefined
): OutputHistoryItem[] {
  if (!storage) return [];

  try {
    const raw = storage.getItem(RECENT_OUTPUT_HISTORY_STORAGE_KEY);
    if (!raw) {
      return [];
    }

    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return [];
    }

    return parsed.filter(isValidHistoryItem).slice(0, RECENT_OUTPUT_HISTORY_LIMIT);
  } catch {
    return [];
  }
}

export function initializeRecentOutputHistoryState(
  baseState: AppState,
  storage: Pick<StorageLike, 'getItem'> | undefined
): AppState {
  const recentOutputs = loadStoredRecentOutputs(storage);

  if (recentOutputs.length === 0) {
    return baseState;
  }

  return { ...baseState, recentOutputs };
}

export function persistRecentOutputs(
  storage: Pick<StorageLike, 'setItem'> | undefined,
  recentOutputs: OutputHistoryItem[]
): void {
  storage?.setItem(
    RECENT_OUTPUT_HISTORY_STORAGE_KEY,
    JSON.stringify(recentOutputs.slice(0, RECENT_OUTPUT_HISTORY_LIMIT))
  );
}
