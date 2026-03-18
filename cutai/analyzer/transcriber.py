"""Audio transcription using faster-whisper (CTranslate2 backend).

Transcribes the audio track of a video file and returns
timestamped segments. faster-whisper is 4-8x faster than
openai-whisper on CPU while maintaining identical accuracy.

Falls back to openai-whisper if faster-whisper is not installed.
"""

from __future__ import annotations

import logging

from cutai.models.types import TranscriptSegment

logger = logging.getLogger(__name__)

VALID_MODELS = ("tiny", "base", "small", "medium", "large")

# Try to import faster_whisper first, fall back to openai-whisper
_USE_FASTER_WHISPER = False
try:
    from faster_whisper import WhisperModel as _FasterWhisperModel
    _USE_FASTER_WHISPER = True
except ImportError:
    _FasterWhisperModel = None  # type: ignore[assignment, misc]


def transcribe(
    video_path: str,
    model_name: str = "base",
    language: str | None = None,
) -> list[TranscriptSegment]:
    """Transcribe audio from a video file using faster-whisper or Whisper.

    Args:
        video_path: Path to the video (or audio) file.
        model_name: Whisper model size (tiny/base/small/medium/large).
        language: Force a specific language, or None for auto-detection.

    Returns:
        List of TranscriptSegment with start/end times, text, and confidence.
    """
    if model_name not in VALID_MODELS:
        logger.warning(
            "Unknown Whisper model '%s', falling back to 'base'", model_name
        )
        model_name = "base"

    if _USE_FASTER_WHISPER:
        return _transcribe_faster_whisper(video_path, model_name, language)
    else:
        logger.info("faster-whisper not available, using openai-whisper (slower)")
        return _transcribe_openai_whisper(video_path, model_name, language)


def _transcribe_faster_whisper(
    video_path: str,
    model_name: str,
    language: str | None,
) -> list[TranscriptSegment]:
    """Transcribe using faster-whisper (CTranslate2, 4-8x faster on CPU)."""
    logger.info("Loading faster-whisper model '%s'...", model_name)

    # Use int8 quantization on CPU for speed; float16 if CUDA is available
    model = _FasterWhisperModel(model_name, device="cpu", compute_type="int8")

    logger.info("Transcribing %s with faster-whisper...", video_path)
    kwargs: dict = {"beam_size": 5, "vad_filter": True}
    if language:
        kwargs["language"] = language

    raw_segments, info = model.transcribe(video_path, **kwargs)

    segments: list[TranscriptSegment] = []
    for seg in raw_segments:
        # faster-whisper provides avg_logprob directly
        raw_logprob = float(seg.avg_logprob) if seg.avg_logprob else -1.0
        confidence = max(0.0, min(1.0, 1.0 + raw_logprob))
        segments.append(
            TranscriptSegment(
                start_time=round(float(seg.start), 3),
                end_time=round(float(seg.end), 3),
                text=seg.text.strip(),
                confidence=round(confidence, 4),
            )
        )

    logger.info(
        "Transcribed %d segments (language=%s, prob=%.2f)",
        len(segments),
        info.language,
        info.language_probability,
    )
    return segments


def _transcribe_openai_whisper(
    video_path: str,
    model_name: str,
    language: str | None,
) -> list[TranscriptSegment]:
    """Transcribe using openai-whisper (original, slower)."""
    logger.info("Loading Whisper model '%s'...", model_name)

    import whisper

    model = whisper.load_model(model_name)

    logger.info("Transcribing %s...", video_path)
    options: dict = {"verbose": False}
    if language:
        options["language"] = language

    result = model.transcribe(video_path, **options)

    segments: list[TranscriptSegment] = []
    for seg in result.get("segments", []):
        # Convert log probability to approximate confidence (0-1)
        raw_logprob = float(seg.get("avg_logprob", -1.0))
        confidence = max(0.0, min(1.0, 1.0 + raw_logprob))
        segments.append(
            TranscriptSegment(
                start_time=round(float(seg["start"]), 3),
                end_time=round(float(seg["end"]), 3),
                text=seg["text"].strip(),
                confidence=round(confidence, 4),
            )
        )

    logger.info("Transcribed %d segments", len(segments))
    return segments
