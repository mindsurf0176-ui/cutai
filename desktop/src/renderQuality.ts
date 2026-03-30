import { RENDER_PRESET_OPTIONS, type MediaJobResult } from './types';

type QualitySource = Pick<
  MediaJobResult,
  'render_preset' | 'resolution' | 'subtitle_export_mode'
> | null | undefined;

export function formatSubtitleExportModeLabel(
  subtitleExportMode: MediaJobResult['subtitle_export_mode']
): string | null {
  if (subtitleExportMode === 'burned') {
    return 'Burned subtitles';
  }

  if (subtitleExportMode === 'sidecar') {
    return 'Sidecar subtitles';
  }

  return null;
}

export function formatRenderQualityDetails(media: QualitySource): string | null {
  if (!media) {
    return null;
  }

  const parts: string[] = [];

  if (media.render_preset) {
    const preset = RENDER_PRESET_OPTIONS.find((option) => option.value === media.render_preset);
    if (preset) {
      parts.push(preset.label);
    }
  }

  if (typeof media.resolution === 'number') {
    parts.push(`${media.resolution}p`);
  }

  const subtitleDetails = formatSubtitleExportModeLabel(media.subtitle_export_mode);
  if (subtitleDetails) {
    parts.push(subtitleDetails);
  }

  return parts.length > 0 ? parts.join(' · ') : null;
}
