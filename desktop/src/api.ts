import { invoke } from '@tauri-apps/api/core';
import type { VideoInfo, VideoAnalysis, EditPlan, Job, Preset } from './types';

const API_BASE = 'http://127.0.0.1:18910';

interface BackendStartResponse {
  started: boolean;
  already_running: boolean;
  port: number;
}

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  let res: Response;

  try {
    res = await fetch(`${API_BASE}${path}`, options);
  } catch (error) {
    throw new Error(
      error instanceof Error ? error.message : 'Unable to reach the CutAI backend'
    );
  }

  if (!res.ok) {
    const text = await res.text().catch(() => 'Unknown error');
    throw new ApiError(res.status, text);
  }
  return res.json() as Promise<T>;
}

export function canAutoStartBackend(): boolean {
  const runtimeWindow = globalThis.window as
    | (Window & { __TAURI_INTERNALS__?: unknown })
    | undefined;

  return Boolean(runtimeWindow?.__TAURI_INTERNALS__);
}

export async function startBackend(): Promise<BackendStartResponse> {
  return invoke<BackendStartResponse>('start_backend');
}

export async function healthCheck(): Promise<boolean> {
  try {
    await fetch(`${API_BASE}/api/health`, { signal: AbortSignal.timeout(3000) });
    return true;
  } catch {
    return false;
  }
}

export async function uploadVideo(
  file: File,
  onProgress?: (progress: number) => void
): Promise<{ video_id: string }> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', `${API_BASE}/api/videos/upload`);

    xhr.upload.addEventListener('progress', (e) => {
      if (e.lengthComputable && onProgress) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    });

    xhr.addEventListener('load', () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText));
      } else {
        reject(new ApiError(xhr.status, xhr.responseText));
      }
    });

    xhr.addEventListener('error', () => reject(new Error('Upload failed')));
    xhr.addEventListener('abort', () => reject(new Error('Upload aborted')));

    const formData = new FormData();
    formData.append('file', file);
    xhr.send(formData);
  });
}

export async function getVideoInfo(videoId: string): Promise<VideoInfo> {
  return request<VideoInfo>(`/api/videos/${videoId}`);
}

export function getThumbnailUrl(videoId: string, time: number = 5.0): string {
  return `${API_BASE}/api/videos/${videoId}/thumbnail?time=${time}`;
}

export async function analyzeVideo(videoId: string): Promise<{ job_id: string }> {
  return request<{ job_id: string }>(`/api/videos/${videoId}/analyze`, {
    method: 'POST',
  });
}

export async function pollJob(jobId: string): Promise<Job> {
  return request<Job>(`/api/jobs/${jobId}`);
}

export async function createPlan(
  videoId: string,
  instruction: string,
  useLlm: boolean = true
): Promise<EditPlan> {
  return request<EditPlan>('/api/plan', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ video_id: videoId, instruction, use_llm: useLlm }),
  });
}

export async function startRender(
  videoId: string,
  plan: EditPlan,
  burnSubtitles: boolean = true
): Promise<{ job_id: string }> {
  return request<{ job_id: string }>('/api/render', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ video_id: videoId, plan, burn_subtitles: burnSubtitles }),
  });
}

export function getDownloadUrl(jobId: string): string {
  return `${API_BASE}/api/render/${jobId}/download`;
}

export async function getPresets(): Promise<Preset[]> {
  return request<Preset[]>('/api/styles/presets');
}

export async function applyStyle(
  videoId: string,
  style: string
): Promise<{ job_id: string }> {
  return request<{ job_id: string }>('/api/styles/apply', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ video_id: videoId, style }),
  });
}

export async function generateHighlights(
  videoId: string,
  targetDuration: number,
  style: string
): Promise<{ job_id: string }> {
  return request<{ job_id: string }>('/api/highlights', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ video_id: videoId, target_duration: targetDuration, style }),
  });
}

export function connectProgressWs(
  jobId: string,
  onProgress: (data: { progress: number; status: string }) => void,
  onClose?: () => void
): WebSocket {
  const ws = new WebSocket(`ws://127.0.0.1:18910/ws/progress/${jobId}`);
  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      onProgress(data);
    } catch {
      // ignore parse errors
    }
  };
  ws.onclose = () => onClose?.();
  ws.onerror = () => onClose?.();
  return ws;
}

export async function getAnalysis(videoId: string): Promise<VideoAnalysis> {
  return request<VideoAnalysis>(`/api/videos/${videoId}/analysis`);
}
