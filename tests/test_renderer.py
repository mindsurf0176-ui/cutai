"""Tests for transcript timestamp adjustment during rendering."""

from __future__ import annotations

from cutai.editor.renderer import _adjust_transcript_for_cuts
from cutai.models.types import CutOperation, TranscriptSegment


class TestAdjustTranscriptForCuts:
    def test_keeps_partially_overlapping_segment_at_start(self):
        transcript = [
            TranscriptSegment(start_time=0.0, end_time=2.0, text="Alphabravo"),
            TranscriptSegment(start_time=2.0, end_time=3.0, text="Charlie Delta"),
        ]
        cut_ops = [
            CutOperation(action="remove", start_time=0.831, end_time=2.072),
        ]

        adjusted = _adjust_transcript_for_cuts(transcript, cut_ops)

        assert [seg.text for seg in adjusted] == ["Alphabravo", "Charlie Delta"]
        assert adjusted[0].start_time == 0.0
        assert adjusted[0].end_time == 0.831
        assert adjusted[1].start_time == 0.831
        assert adjusted[1].end_time == 1.759
