import { describe, expect, it, vi } from 'vitest';
import { initialState } from './store';
import {
  SUBTITLE_EXPORT_MODE_STORAGE_KEY,
  initializeSubtitleExportModeState,
  loadStoredSubtitleExportMode,
  persistSubtitleExportMode,
} from './subtitleExportModeStorage';

describe('subtitle export mode persistence', () => {
  it('loads a valid stored subtitle export mode into initial state', () => {
    const state = initializeSubtitleExportModeState(initialState, {
      getItem: vi.fn().mockReturnValue('sidecar'),
    });

    expect(state.subtitleExportMode).toBe('sidecar');
  });

  it('ignores missing or invalid stored values', () => {
    expect(loadStoredSubtitleExportMode(undefined)).toBeNull();
    expect(
      loadStoredSubtitleExportMode({
        getItem: vi.fn().mockReturnValue('embedded'),
      })
    ).toBeNull();
  });

  it('persists the selected subtitle export mode', () => {
    const setItem = vi.fn();

    persistSubtitleExportMode({ setItem }, 'burned');

    expect(setItem).toHaveBeenCalledWith(SUBTITLE_EXPORT_MODE_STORAGE_KEY, 'burned');
  });
});
