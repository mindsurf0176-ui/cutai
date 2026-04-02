"""Tests for performance modules — cache, hwaccel, transcriber backend selection."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch

from cutai.models.types import (
    QualityReport,
    VideoAnalysis,
)


# ── Cache tests ──────────────────────────────────────────────────────────────


class TestAnalysisCache:
    def test_cache_miss(self, tmp_path):
        from cutai.analyzer.cache import get_cached

        video = tmp_path / "test.mp4"
        video.write_bytes(b"\x00" * 100)

        result = get_cached(str(video), whisper_model="base")
        assert result is None

    def test_cache_roundtrip(self, tmp_path):
        from cutai.analyzer.cache import get_cached, save_cache

        video = tmp_path / "test.mp4"
        video.write_bytes(b"\x00" * 100)

        analysis = VideoAnalysis(
            file_path=str(video),
            duration=60.0,
            fps=30.0,
            width=1920,
            height=1080,
            scenes=[],
            transcript=[],
            quality=QualityReport(),
        )

        save_cache(str(video), analysis, whisper_model="base")
        cached = get_cached(str(video), whisper_model="base")

        assert cached is not None
        assert cached.duration == 60.0
        assert cached.width == 1920

    def test_different_model_different_cache(self, tmp_path):
        from cutai.analyzer.cache import get_cached, save_cache

        video = tmp_path / "test.mp4"
        video.write_bytes(b"\x00" * 100)

        analysis = VideoAnalysis(
            file_path=str(video),
            duration=60.0,
            fps=30.0,
            width=1920,
            height=1080,
        )

        save_cache(str(video), analysis, whisper_model="base")

        # Different whisper model = different cache key
        cached = get_cached(str(video), whisper_model="large")
        assert cached is None

    def test_clear_cache(self, tmp_path):
        from cutai.analyzer.cache import clear_cache, get_cached, save_cache

        video = tmp_path / "test.mp4"
        video.write_bytes(b"\x00" * 100)

        analysis = VideoAnalysis(
            file_path=str(video),
            duration=60.0,
            fps=30.0,
            width=1920,
            height=1080,
        )

        save_cache(str(video), analysis, whisper_model="base")
        assert get_cached(str(video)) is not None

        count = clear_cache(str(video))
        assert count >= 1
        assert get_cached(str(video)) is None


# ── Hardware acceleration tests ──────────────────────────────────────────────


class TestHWAccel:
    def test_detect_returns_valid_backend(self):
        from cutai.hwaccel import detect_hwaccel
        # Clear cache for fresh detection
        detect_hwaccel.cache_clear()
        backend = detect_hwaccel()
        assert backend in ("videotoolbox", "nvenc", "vaapi", "software")

    def test_get_encode_flags_software(self):
        from cutai.hwaccel import get_encode_flags
        flags = get_encode_flags("software", "h264", "balanced")
        assert "-c:v" in flags
        assert "libx264" in flags

    def test_get_encode_flags_videotoolbox(self):
        from cutai.hwaccel import get_encode_flags
        flags = get_encode_flags("videotoolbox", "h264", "balanced")
        assert "h264_videotoolbox" in flags

    def test_get_encode_flags_hevc(self):
        from cutai.hwaccel import get_encode_flags
        flags = get_encode_flags("software", "hevc", "quality")
        assert "libx265" in flags
        assert "slow" in flags

    def test_hwaccel_info(self):
        from cutai.hwaccel import get_hwaccel_info
        info = get_hwaccel_info()
        assert "backend" in info
        assert "system" in info
        assert "accelerated" in info


# ── Transcriber backend detection tests ──────────────────────────────────────


class TestTranscriberBackend:
    def test_backend_is_set(self):
        from cutai.analyzer.transcriber import _BACKEND
        assert _BACKEND in ("mlx-whisper", "faster-whisper", "openai-whisper")

    def test_valid_model_check(self):
        from cutai.analyzer.transcriber import VALID_MODELS
        assert "base" in VALID_MODELS
        assert "large" in VALID_MODELS
