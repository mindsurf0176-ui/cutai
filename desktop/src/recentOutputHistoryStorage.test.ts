import { describe, expect, it, vi } from 'vitest';
import { initialState, RECENT_OUTPUT_HISTORY_LIMIT, type AppState } from './store';
import {
  initializeRecentOutputHistoryState,
  loadStoredRecentOutputs,
  persistRecentOutputs,
  RECENT_OUTPUT_HISTORY_STORAGE_KEY,
} from './recentOutputHistoryStorage';
import type { OutputHistoryItem } from './types';

function createItem(index: number): OutputHistoryItem {
  return {
    kind: index % 2 === 0 ? 'preview' : 'render',
    job_id: `job-${index}`,
    output_path: `/tmp/output-${index}.mp4`,
    resolution: 360 + index,
    render_preset: index % 2 === 0 ? undefined : 'balanced',
    subtitle_export_mode: index % 2 === 0 ? undefined : 'sidecar',
    subtitle_path: index % 2 === 0 ? undefined : `/tmp/output-${index}.ass`,
    original_name: `clip-${index}.mp4`,
    completed_at: `2026-03-28T00:00:${String(index).padStart(2, '0')}Z`,
  };
}

function createState(overrides: Partial<AppState> = {}): AppState {
  return {
    ...initialState,
    backendStatus: 'online',
    backendOnline: true,
    ...overrides,
  };
}

describe('recent output history storage', () => {
  it('loads only valid recent outputs and enforces the history limit', () => {
    const items = Array.from({ length: RECENT_OUTPUT_HISTORY_LIMIT + 2 }, (_, index) => createItem(index));
    const storage = {
      getItem: vi.fn(() => JSON.stringify([
        items[0],
        { invalid: true },
        ...items.slice(1),
      ])),
    };

    const loaded = loadStoredRecentOutputs(storage);

    expect(storage.getItem).toHaveBeenCalledWith(RECENT_OUTPUT_HISTORY_STORAGE_KEY);
    expect(loaded).toHaveLength(RECENT_OUTPUT_HISTORY_LIMIT);
    expect(loaded[0]).toEqual(items[0]);
    expect(loaded[loaded.length - 1]).toEqual(items[RECENT_OUTPUT_HISTORY_LIMIT - 1]);
  });

  it('initializes state with stored recent outputs when available', () => {
    const recentOutputs = [createItem(0), createItem(1)];
    const storage = {
      getItem: vi.fn(() => JSON.stringify(recentOutputs)),
    };

    const nextState = initializeRecentOutputHistoryState(createState(), storage);

    expect(nextState.recentOutputs).toEqual(recentOutputs);
    expect(nextState.videoId).toBe(initialState.videoId);
  });

  it('persists a truncated recent output history payload', () => {
    const recentOutputs = Array.from({ length: RECENT_OUTPUT_HISTORY_LIMIT + 3 }, (_, index) => createItem(index));
    const storage = {
      setItem: vi.fn(),
    };

    persistRecentOutputs(storage, recentOutputs);

    expect(storage.setItem).toHaveBeenCalledWith(
      RECENT_OUTPUT_HISTORY_STORAGE_KEY,
      JSON.stringify(recentOutputs.slice(0, RECENT_OUTPUT_HISTORY_LIMIT))
    );
  });
});
