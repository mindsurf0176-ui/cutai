import { SUBTITLE_EXPORT_MODE_OPTIONS, type SubtitleExportMode } from './types';
import type { AppState } from './store';

export const SUBTITLE_EXPORT_MODE_STORAGE_KEY = 'cutai.desktop.subtitleExportMode';

interface StorageLike {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

const VALID_SUBTITLE_EXPORT_MODES = new Set<SubtitleExportMode>(
  SUBTITLE_EXPORT_MODE_OPTIONS.map((option) => option.value)
);

export function loadStoredSubtitleExportMode(
  storage: Pick<StorageLike, 'getItem'> | undefined
): SubtitleExportMode | null {
  if (!storage) return null;

  const savedMode = storage.getItem(SUBTITLE_EXPORT_MODE_STORAGE_KEY) as SubtitleExportMode | null;

  if (savedMode && VALID_SUBTITLE_EXPORT_MODES.has(savedMode)) {
    return savedMode;
  }

  return null;
}

export function initializeSubtitleExportModeState(
  baseState: AppState,
  storage: Pick<StorageLike, 'getItem'> | undefined
): AppState {
  const subtitleExportMode = loadStoredSubtitleExportMode(storage);

  if (subtitleExportMode === null) {
    return baseState;
  }

  return { ...baseState, subtitleExportMode };
}

export function persistSubtitleExportMode(
  storage: Pick<StorageLike, 'setItem'> | undefined,
  subtitleExportMode: SubtitleExportMode
): void {
  storage?.setItem(SUBTITLE_EXPORT_MODE_STORAGE_KEY, subtitleExportMode);
}
