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

function getButton(container: HTMLElement, label: string): HTMLButtonElement {
  const button = Array.from(container.querySelectorAll('button')).find(
    (candidate) => candidate.textContent?.trim() === label
  );

  if (!button) {
    throw new Error(`Button not found: ${label}`);
  }

  return button as HTMLButtonElement;
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

describe('JobProgress export feedback', () => {
  afterEach(async () => {
    delete (window as Window & { __TAURI_INTERNALS__?: unknown }).__TAURI_INTERNALS__;
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

  it('shows saved-path actions after a desktop render export completes', async () => {
    (window as Window & { __TAURI_INTERNALS__?: unknown }).__TAURI_INTERNALS__ = {};

    vi.spyOn(api, 'pollJob').mockResolvedValue({
      job_id: 'render-job-1',
      type: 'render',
      status: 'completed',
      progress: 100,
      result: {
        output_path: '/tmp/render.mp4',
        resolution: 1080,
        render_preset: 'balanced',
        subtitle_export_mode: 'sidecar',
        subtitle_path: '/tmp/render.ass',
        export_artifacts: [
          { kind: 'video', path: '/tmp/render.mp4' },
          { kind: 'subtitle', path: '/tmp/render.ass' },
        ],
      },
    });
    vi.spyOn(api, 'connectProgressWs').mockImplementation(() => ({ close() {} } as WebSocket));
    const exportSpy = vi
      .spyOn(api, 'exportBundleOrUrl')
      .mockResolvedValue({
        savedPrimaryPath: '/Users/minseo/Exports/clip-render.mp4',
        savedCompanionPaths: ['/Users/minseo/Exports/clip-render.ass'],
      });
    const openSpy = vi.spyOn(api, 'openPathOrUrl').mockResolvedValue();
    const revealSpy = vi.spyOn(api, 'revealPathOrUrl').mockResolvedValue();

    await renderProgress(
      createState({
        activeJob: {
          job_id: 'render-job-1',
          type: 'render',
          status: 'completed',
          progress: 100,
          result: {
            output_path: '/tmp/render.mp4',
            resolution: 1080,
            render_preset: 'balanced',
            subtitle_export_mode: 'sidecar',
            subtitle_path: '/tmp/render.ass',
            export_artifacts: [
              { kind: 'video', path: '/tmp/render.mp4' },
              { kind: 'subtitle', path: '/tmp/render.ass' },
            ],
          },
        },
      })
    );

    if (!container) {
      throw new Error('Missing test container');
    }

    expect(container.textContent).toContain('Render complete');
    expect(container.textContent).toContain('Output: Balanced · 1080p · Sidecar subtitles');
    expect(container.textContent).toContain('Subtitle file: /tmp/render.ass');

    await act(async () => {
      getButton(container!, 'Export render').click();
    });

    expect(exportSpy).toHaveBeenCalledWith(
      {
        output_path: '/tmp/render.mp4',
        resolution: 1080,
        render_preset: 'balanced',
        subtitle_export_mode: 'sidecar',
        subtitle_path: '/tmp/render.ass',
        export_artifacts: [
          { kind: 'video', path: '/tmp/render.mp4' },
          { kind: 'subtitle', path: '/tmp/render.ass' },
        ],
      },
      'clip-render.mp4',
      'http://127.0.0.1:18910/api/render/render-job-1/download',
    );
    expect(container.textContent).toContain('Render saved');
    expect(container.textContent).toContain('Balanced · 1080p · Sidecar subtitles');
    expect(container.textContent).toContain('/Users/minseo/Exports/clip-render.mp4');

    await act(async () => {
      getButton(container!, 'Reveal in folder').click();
    });
    expect(revealSpy).toHaveBeenCalledWith('/Users/minseo/Exports/clip-render.mp4');

    await act(async () => {
      getButton(container!, 'Open file').click();
    });
    expect(openSpy).toHaveBeenCalledWith('/Users/minseo/Exports/clip-render.mp4');
  });
});
