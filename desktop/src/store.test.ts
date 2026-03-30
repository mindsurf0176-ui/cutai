import { describe, expect, it } from 'vitest';
import { appReducer, initialState, type AppState } from './store';

function createState(overrides: Partial<AppState> = {}): AppState {
  return {
    ...initialState,
    backendStatus: 'online',
    backendOnline: true,
    presets: [{ name: 'preset', description: 'Preset' }],
    ...overrides,
  };
}

describe('appReducer preview resolution behavior', () => {
  it('SET_PREVIEW_RESOLUTION updates previewResolution and clears previewResult', () => {
    const state = createState({
      previewResolution: 360,
      previewResult: { job_id: 'preview-job', output_path: '/tmp/preview.mp4', resolution: 360 },
    });

    const nextState = appReducer(state, { type: 'SET_PREVIEW_RESOLUTION', resolution: 720 });

    expect(nextState.previewResolution).toBe(720);
    expect(nextState.previewResult).toBeNull();
  });

  it('RESET preserves previewResolution while resetting editor state', () => {
    const state = createState({
      videoId: 'video-1',
      videoInfo: {
        video_id: 'video-1',
        original_name: 'clip.mp4',
        duration: 30,
        width: 1920,
        height: 1080,
        fps: 30,
        file_size: 1024,
      },
      analysis: {
        file_path: '/tmp/clip.mp4',
        duration: 30,
        fps: 30,
        width: 1920,
        height: 1080,
        scenes: [],
        transcript: [],
        quality: { silent_segments: [], audio_energy: [], overall_silence_ratio: 0 },
      },
      editPlan: { instruction: 'trim', operations: [], estimated_duration: 20, summary: 'Trim' },
      activeJob: { job_id: 'job-1', type: 'preview', status: 'running', progress: 50 },
      previewResult: { job_id: 'preview-job', output_path: '/tmp/preview.mp4', resolution: 720 },
      renderResult: { job_id: 'render-job', output_path: '/tmp/render.mp4' },
      previewResolution: 720,
      renderPreset: 'high',
      subtitleExportMode: 'sidecar',
      view: 'editor',
      sidebarTab: 'style',
      uploadProgress: 90,
      error: 'problem',
      currentTime: 12,
    });

    const nextState = appReducer(state, { type: 'RESET' });

    expect(nextState.previewResolution).toBe(720);
    expect(nextState.renderPreset).toBe('high');
    expect(nextState.subtitleExportMode).toBe('sidecar');
    expect(nextState.videoId).toBeNull();
    expect(nextState.videoInfo).toBeNull();
    expect(nextState.analysis).toBeNull();
    expect(nextState.editPlan).toBeNull();
    expect(nextState.activeJob).toBeNull();
    expect(nextState.previewResult).toBeNull();
    expect(nextState.renderResult).toBeNull();
    expect(nextState.view).toBe(initialState.view);
    expect(nextState.sidebarTab).toBe(initialState.sidebarTab);
    expect(nextState.uploadProgress).toBe(initialState.uploadProgress);
    expect(nextState.error).toBeNull();
    expect(nextState.currentTime).toBe(initialState.currentTime);
    expect(nextState.backendStatus).toBe(state.backendStatus);
    expect(nextState.backendOnline).toBe(state.backendOnline);
    expect(nextState.backendError).toBe(state.backendError);
    expect(nextState.presets).toBe(state.presets);
  });

  it('SET_RENDER_PRESET updates renderPreset and clears renderResult', () => {
    const state = createState({
      renderPreset: 'balanced',
      renderResult: { job_id: 'render-job', output_path: '/tmp/render.mp4', render_preset: 'balanced' },
    });

    const nextState = appReducer(state, { type: 'SET_RENDER_PRESET', renderPreset: 'draft' });

    expect(nextState.renderPreset).toBe('draft');
    expect(nextState.renderResult).toBeNull();
  });

  it('SET_SUBTITLE_EXPORT_MODE updates subtitleExportMode and clears renderResult', () => {
    const state = createState({
      subtitleExportMode: 'burned',
      renderResult: { job_id: 'render-job', output_path: '/tmp/render.mp4', subtitle_export_mode: 'burned' },
    });

    const nextState = appReducer(state, {
      type: 'SET_SUBTITLE_EXPORT_MODE',
      subtitleExportMode: 'sidecar',
    });

    expect(nextState.subtitleExportMode).toBe('sidecar');
    expect(nextState.renderResult).toBeNull();
  });

  it('ADD_RECENT_OUTPUT prepends new items, de-duplicates by kind and job id, and enforces the limit', () => {
    const recentOutputs = Array.from({ length: 12 }, (_, index) => ({
      kind: index % 2 === 0 ? 'preview' : 'render',
      job_id: `job-${index}`,
      output_path: `/tmp/output-${index}.mp4`,
      completed_at: `2026-03-28T00:00:${String(index).padStart(2, '0')}Z`,
    })) as AppState['recentOutputs'];
    const state = createState({ recentOutputs });

    const deduped = appReducer(state, {
      type: 'ADD_RECENT_OUTPUT',
      item: {
        kind: 'render',
        job_id: 'job-1',
        output_path: '/tmp/output-1-new.mp4',
        resolution: 1080,
        subtitle_export_mode: 'sidecar',
        subtitle_path: '/tmp/output-1-new.ass',
        completed_at: '2026-03-28T00:01:00Z',
      },
    });

    expect(deduped.recentOutputs).toHaveLength(12);
    expect(deduped.recentOutputs[0]).toEqual({
      kind: 'render',
      job_id: 'job-1',
      output_path: '/tmp/output-1-new.mp4',
      resolution: 1080,
      subtitle_export_mode: 'sidecar',
      subtitle_path: '/tmp/output-1-new.ass',
      completed_at: '2026-03-28T00:01:00Z',
    });
    expect(deduped.recentOutputs.filter((item) => item.kind === 'render' && item.job_id === 'job-1')).toHaveLength(1);

    const appended = appReducer(deduped, {
      type: 'ADD_RECENT_OUTPUT',
      item: {
        kind: 'preview',
        job_id: 'job-new',
        output_path: '/tmp/output-new.mp4',
        completed_at: '2026-03-28T00:02:00Z',
      },
    });

    expect(appended.recentOutputs).toHaveLength(12);
    expect(appended.recentOutputs[0].job_id).toBe('job-new');
    expect(appended.recentOutputs.some((item) => item.job_id === 'job-11')).toBe(false);
  });

  it('tracks the selected planning style preset and preserves it across reset', () => {
    const preset = { name: 'cinematic', description: 'Warm contrast', file: 'cinematic.yaml' };
    const selected = appReducer(createState(), {
      type: 'SET_PLANNING_STYLE_PRESET',
      preset,
    });

    expect(selected.planningStylePreset).toEqual(preset);

    const reset = appReducer(selected, { type: 'RESET' });

    expect(reset.planningStylePreset).toEqual(preset);
  });

  it('clears the selected planning style preset explicitly', () => {
    const preset = { name: 'cinematic', description: 'Warm contrast', file: 'cinematic.yaml' };
    const selected = appReducer(createState(), {
      type: 'SET_PLANNING_STYLE_PRESET',
      preset,
    });

    const cleared = appReducer(selected, {
      type: 'SET_PLANNING_STYLE_PRESET',
      preset: null,
    });

    expect(cleared.planningStylePreset).toBeNull();
  });
});
