import { useMemo } from 'react';
import { GripHorizontal } from 'lucide-react';
import * as Slider from '@radix-ui/react-slider';
import { useApp } from '../store';
import { getThumbnailUrl } from '../api';
import SceneTimeline from './SceneTimeline';

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

export default function VideoPreview() {
  const { state, dispatch } = useApp();
  const { videoId, videoInfo, analysis, currentTime } = state;

  const thumbnailUrl = useMemo(() => {
    if (!videoId) return null;
    return getThumbnailUrl(videoId, currentTime);
  }, [videoId, currentTime]);

  if (!videoId || !videoInfo) {
    return (
      <div className="flex items-center justify-center h-full text-[var(--text-secondary)]">
        <p>No video loaded</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full gap-3">
      {/* Video thumbnail area */}
      <div className="relative flex-1 min-h-0 bg-black rounded-lg overflow-hidden flex items-center justify-center">
        {thumbnailUrl ? (
          <img
            src={thumbnailUrl}
            alt="Video frame"
            className="max-w-full max-h-full object-contain"
            onError={(e) => {
              (e.target as HTMLImageElement).style.display = 'none';
            }}
          />
        ) : (
          <div className="text-[var(--text-secondary)] text-sm">Loading preview...</div>
        )}

        {/* Preview mode overlay */}
        <div className="absolute inset-x-0 bottom-3 flex justify-center pointer-events-none">
          <div className="inline-flex items-center gap-2 rounded-full bg-black/65 px-3 py-1.5 text-xs text-white backdrop-blur-sm">
            <GripHorizontal size={14} />
            <span>Scrub timeline to preview frames</span>
          </div>
        </div>

        {/* Video info badge */}
        <div className="absolute top-3 right-3 bg-black/60 backdrop-blur-sm rounded-md px-2 py-1 text-xs text-[var(--text-secondary)]">
          {videoInfo.width}×{videoInfo.height} · {videoInfo.fps}fps
        </div>
      </div>

      {/* Scene timeline (if analysis available) */}
      {analysis && <SceneTimeline />}

      {/* Timeline controls */}
      <div className="flex items-center gap-3 px-2">
        <div
          className="w-8 h-8 rounded-full bg-[var(--bg-tertiary)] flex items-center justify-center text-[var(--text-secondary)]"
          aria-label="Frame preview only"
          title="Playback is not available yet"
        >
          <GripHorizontal size={14} />
        </div>

        <span className="text-xs text-[var(--text-secondary)] w-12 text-right tabular-nums">
          {formatTime(currentTime)}
        </span>

        <Slider.Root
          className="relative flex-1 flex items-center h-5 select-none touch-none"
          value={[currentTime]}
          max={videoInfo.duration}
          step={0.1}
          onValueChange={([val]) => dispatch({ type: 'SET_CURRENT_TIME', time: val })}
        >
          <Slider.Track className="relative h-1 flex-1 rounded-full bg-[var(--bg-tertiary)]">
            <Slider.Range className="absolute h-full rounded-full bg-[var(--accent)]" />
          </Slider.Track>
          <Slider.Thumb className="block w-3 h-3 rounded-full bg-[var(--accent)] hover:bg-[var(--accent-hover)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/50 transition-colors cursor-pointer" />
        </Slider.Root>

        <span className="text-xs text-[var(--text-secondary)] w-12 tabular-nums">
          {formatTime(videoInfo.duration)}
        </span>
      </div>
    </div>
  );
}
