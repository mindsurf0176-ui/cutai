export interface VideoInfo {
  video_id: string;
  original_name: string;
  duration: number;
  width: number;
  height: number;
  fps: number;
  file_size: number;
}

export interface SceneInfo {
  id: number;
  start_time: number;
  end_time: number;
  duration: number;
  has_speech: boolean;
  is_silent: boolean;
  engagement_score?: number;
}

export interface VideoAnalysis {
  file_path: string;
  duration: number;
  fps: number;
  width: number;
  height: number;
  scenes: SceneInfo[];
  transcript: Array<Record<string, unknown>>;
  quality: {
    silent_segments: Array<Record<string, unknown>>;
    audio_energy: number[];
    overall_silence_ratio: number;
  };
}

export interface EditOperation {
  type: 'cut' | 'subtitle' | 'bgm' | 'colorgrade' | 'transition' | 'speed';
  start_time?: number;
  end_time?: number;
  description?: string;
  [key: string]: unknown;
}

export interface EditPlan {
  instruction: string;
  operations: EditOperation[];
  estimated_duration: number;
  summary: string;
}

export interface Job {
  job_id: string;
  type?: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress: number;
  result?: Record<string, unknown>;
  error?: string;
}

export interface Preset {
  name: string;
  description: string;
  style?: Record<string, unknown>;
}

export interface EditDNA {
  rhythm: number;
  visual: number;
  audio: number;
}
