import { describe, expect, it, vi } from 'vitest';
import { initialState } from './store';
import {
  RENDER_PRESET_STORAGE_KEY,
  initializeRenderPresetState,
  loadStoredRenderPreset,
  persistRenderPreset,
} from './renderPresetStorage';

describe('render preset persistence', () => {
  it('loads a valid stored render preset into initial state', () => {
    const state = initializeRenderPresetState(initialState, {
      getItem: vi.fn().mockReturnValue('high'),
    });

    expect(state.renderPreset).toBe('high');
  });

  it('ignores missing or invalid stored values', () => {
    expect(loadStoredRenderPreset(undefined)).toBeNull();
    expect(
      loadStoredRenderPreset({
        getItem: vi.fn().mockReturnValue('ultra'),
      })
    ).toBeNull();
  });

  it('persists the selected render preset', () => {
    const setItem = vi.fn();

    persistRenderPreset({ setItem }, 'balanced');

    expect(setItem).toHaveBeenCalledWith(RENDER_PRESET_STORAGE_KEY, 'balanced');
  });
});
