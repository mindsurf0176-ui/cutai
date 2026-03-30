import { PREVIEW_RESOLUTIONS, type PreviewResolution } from './types';
import type { AppState } from './store';

export const PREVIEW_RESOLUTION_STORAGE_KEY = 'cutai.desktop.previewResolution';

interface StorageLike {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

export function loadStoredPreviewResolution(
  storage: Pick<StorageLike, 'getItem'> | undefined
): PreviewResolution | null {
  if (!storage) return null;

  const savedResolution = Number.parseInt(
    storage.getItem(PREVIEW_RESOLUTION_STORAGE_KEY) ?? '',
    10
  );

  if (PREVIEW_RESOLUTIONS.includes(savedResolution as PreviewResolution)) {
    return savedResolution as PreviewResolution;
  }

  return null;
}

export function initializeAppState(
  baseState: AppState,
  storage: Pick<StorageLike, 'getItem'> | undefined
): AppState {
  const previewResolution = loadStoredPreviewResolution(storage);

  if (previewResolution === null) {
    return baseState;
  }

  return { ...baseState, previewResolution };
}

export function persistPreviewResolution(
  storage: Pick<StorageLike, 'setItem'> | undefined,
  resolution: PreviewResolution
): void {
  storage?.setItem(PREVIEW_RESOLUTION_STORAGE_KEY, String(resolution));
}
