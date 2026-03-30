import { describe, expect, it, vi } from 'vitest';
import { initialState } from './store';
import {
  PREVIEW_RESOLUTION_STORAGE_KEY,
  initializeAppState,
  loadStoredPreviewResolution,
  persistPreviewResolution,
} from './previewResolutionStorage';

describe('preview resolution persistence', () => {
  it('loads a valid stored preview resolution into initial state', () => {
    const state = initializeAppState(initialState, {
      getItem: vi.fn().mockReturnValue('720'),
    });

    expect(state.previewResolution).toBe(720);
  });

  it('ignores missing or invalid stored values', () => {
    expect(loadStoredPreviewResolution(undefined)).toBeNull();
    expect(
      loadStoredPreviewResolution({
        getItem: vi.fn().mockReturnValue('999'),
      })
    ).toBeNull();
    expect(
      loadStoredPreviewResolution({
        getItem: vi.fn().mockReturnValue('not-a-number'),
      })
    ).toBeNull();
  });

  it('persists the selected preview resolution', () => {
    const setItem = vi.fn();

    persistPreviewResolution({ setItem }, 480);

    expect(setItem).toHaveBeenCalledWith(PREVIEW_RESOLUTION_STORAGE_KEY, '480');
  });
});
