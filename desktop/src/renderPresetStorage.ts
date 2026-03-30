import { RENDER_PRESET_OPTIONS, type RenderPreset } from './types';
import type { AppState } from './store';

export const RENDER_PRESET_STORAGE_KEY = 'cutai.desktop.renderPreset';

interface StorageLike {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

const VALID_RENDER_PRESETS = new Set<RenderPreset>(
  RENDER_PRESET_OPTIONS.map((preset) => preset.value)
);

export function loadStoredRenderPreset(
  storage: Pick<StorageLike, 'getItem'> | undefined
): RenderPreset | null {
  if (!storage) return null;

  const savedPreset = storage.getItem(RENDER_PRESET_STORAGE_KEY) as RenderPreset | null;

  if (savedPreset && VALID_RENDER_PRESETS.has(savedPreset)) {
    return savedPreset;
  }

  return null;
}

export function initializeRenderPresetState(
  baseState: AppState,
  storage: Pick<StorageLike, 'getItem'> | undefined
): AppState {
  const renderPreset = loadStoredRenderPreset(storage);

  if (renderPreset === null) {
    return baseState;
  }

  return { ...baseState, renderPreset };
}

export function persistRenderPreset(
  storage: Pick<StorageLike, 'setItem'> | undefined,
  renderPreset: RenderPreset
): void {
  storage?.setItem(RENDER_PRESET_STORAGE_KEY, renderPreset);
}
