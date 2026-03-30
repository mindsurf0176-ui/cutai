import { describe, expect, it } from 'vitest';
import {
  formatRenderQualityDetails,
  formatSubtitleExportModeLabel,
} from './renderQuality';

describe('render quality formatting', () => {
  it('includes subtitle export mode details when available', () => {
    expect(
      formatRenderQualityDetails({
        render_preset: 'balanced',
        resolution: 1080,
        subtitle_export_mode: 'sidecar',
      })
    ).toBe('Balanced · 1080p · Sidecar subtitles');
  });

  it('formats subtitle export mode labels', () => {
    expect(formatSubtitleExportModeLabel('burned')).toBe('Burned subtitles');
    expect(formatSubtitleExportModeLabel('sidecar')).toBe('Sidecar subtitles');
    expect(formatSubtitleExportModeLabel(undefined)).toBeNull();
  });
});
