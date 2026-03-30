import { act, useReducer } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, describe, expect, it, vi } from 'vitest';
import JobProgress from './JobProgress';
import { AppContext, appReducer, initialState, type AppState } from '../store';
import type { VideoInfo } from '../types';
import * as api from '../api';

declare global {
  var IS_REACT_ACT_ENVIRONMENT: boolean | undefined;
}

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const videoInfo: VideoInfo = {
  video_id: 'video-1',
  original_name: 'clip.mp4',
  duration: 42,
  width: 1920,
  height: 1080,
  fps: 30,
  file_size: 1_024,
};

let container: HTMLDivElement | null = null;
let root: Root | null = null;

function createState(overrides: Partial<AppState> = {}): AppState {
  return {
    ...initialState,
    backendStatus: 'online',
    backendOnline: true,
    videoId: videoInfo.video_id,
    videoInfo,
    view: 'editor',
    sidebarTab: 'edit',
    ...overrides,
  };
}

function TestHarness({ initial }: { initial: AppState }) {
  const [state, dispatch] = useReducer(appReducer, initial);

  return (
    <AppContext.Provider value={{ state, dispatch }}>
      <JobProgress />
    </AppContext.Provider>
  );
}

async function renderProgress(initial: AppState) {
  container = document.createElement('div');
  document.body.appendChild(container);
  root = createRoot(container);

  await act(async () => {
    root?.render(<TestHarness initial={initial} />);
  });
}

describe('JobProgress preview metadata', () => {
  afterEach(async () => {
    vi.restoreAllMocks();

    if (root) {
      await act(async () => {
        root?.unmount();
      });
      root = null;
    }

    container?.remove();
    container = null;
  });

  it('shows preview resolution on completed preview jobs', async () => {
    vi.spyOn(api, 'pollJob').mockResolvedValue({
      job_id: 'preview-job-1',
      type: 'preview',
      status: 'completed',
      progress: 100,
      result: { output_path: '/tmp/preview.mp4', resolution: 480 },
    });
    vi.spyOn(api, 'connectProgressWs').mockImplementation(() => ({ close() {} } as WebSocket));

    await renderProgress(
      createState({
        activeJob: {
          job_id: 'preview-job-1',
          type: 'preview',
          status: 'completed',
          progress: 100,
          result: { output_path: '/tmp/preview.mp4', resolution: 480 },
        },
      })
    );

    expect(container?.textContent).toContain('Preview ready');
    expect(container?.textContent).toContain('Output: 480p');
  });
});
