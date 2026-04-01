import { useApp } from '../store';

function engagementColor(score: number | undefined): string {
  if (score === undefined) return 'bg-[var(--bg-tertiary)]';
  if (score >= 0.7) return 'bg-[var(--success)]';
  if (score >= 0.4) return 'bg-[var(--warning)]';
  return 'bg-[var(--error)]';
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

export default function SceneTimeline() {
  const { state, dispatch } = useApp();
  const { analysis, videoInfo } = state;

  if (!analysis || !videoInfo) return null;

  const totalDuration = analysis.duration || videoInfo.duration;
  if (totalDuration <= 0) return null;

  const speechDuration = analysis.scenes
    .filter((scene) => scene.has_speech)
    .reduce((sum, scene) => sum + scene.duration, 0);
  const speechRatio = totalDuration > 0 ? speechDuration / totalDuration : 0;
  const silenceRatio = analysis.quality?.overall_silence_ratio ?? 0;

  return (
    <div className="px-2">
      <div className="flex items-center gap-0.5 h-6 rounded-md overflow-hidden">
        {analysis.scenes.map((scene) => {
          const widthPercent = (scene.duration / totalDuration) * 100;
          return (
            <button
              key={scene.id}
              className={`
                h-full ${engagementColor(scene.engagement_score)}
                hover:opacity-80 transition-opacity cursor-pointer
                relative group
              `}
              style={{ width: `${Math.max(widthPercent, 0.5)}%` }}
              onClick={() => dispatch({ type: 'SET_CURRENT_TIME', time: scene.start_time })}
              title={`Scene ${scene.id}: ${formatTime(scene.start_time)} - ${formatTime(scene.end_time)}`}
            >
              <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1 hidden group-hover:block z-10">
                <div className="bg-[var(--bg-primary)] border border-[var(--border-color)] rounded px-2 py-1 text-xs whitespace-nowrap text-[var(--text-primary)]">
                  <span className="font-medium">Scene {scene.id}</span>
                  <br />
                  {formatTime(scene.start_time)} – {formatTime(scene.end_time)}
                  {scene.is_silent && <span className="ml-1 text-xs text-[var(--text-secondary)]">silent</span>}
                  {scene.has_speech && <span className="ml-1 text-[var(--text-secondary)]">speech</span>}
                </div>
              </div>
            </button>
          );
        })}
      </div>
      <div className="flex justify-between mt-1 text-[10px] text-[var(--text-secondary)]">
        <span>{analysis.scenes.length} scenes</span>
        <span>
          {Math.round(speechRatio * 100)}% speech · {Math.round(silenceRatio * 100)}% silence
        </span>
      </div>
    </div>
  );
}
