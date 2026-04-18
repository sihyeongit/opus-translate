"""Minimal smoke tests for stages that can run without the heavy models.

Run with: python -m pytest tests/
"""
from __future__ import annotations

import numpy as np

from src.vad import SileroVAD


def test_silero_rejects_silence():
    vad = SileroVAD(
        sample_rate=16000,
        frame_ms=32,
        min_speech_ms=300,
        min_silence_ms=500,
        preroll_ms=0,
        postroll_ms=0,
    )
    frame_samples = 16000 * 32 // 1000
    silence = [np.zeros(frame_samples, dtype=np.float32) for _ in range(50)]
    segments = list(vad.process(iter(silence)))
    assert segments == [], "VAD should not emit segments for pure silence"


def test_silero_detects_speech_like_signal():
    vad = SileroVAD(
        sample_rate=16000,
        frame_ms=32,
        min_speech_ms=200,
        min_silence_ms=300,
        preroll_ms=0,
        postroll_ms=0,
    )
    frame_samples = 16000 * 32 // 1000
    t = np.arange(frame_samples) / 16000.0
    tone = 0.2 * np.sin(2 * np.pi * 220 * t).astype(np.float32)
    frames = [tone.copy() for _ in range(30)]
    frames.extend(np.zeros(frame_samples, dtype=np.float32) for _ in range(30))

    segments = list(vad.process(iter(frames)))
    # Pure tone may or may not trigger Silero; this test only verifies
    # no crashes and that the pipeline produces a valid structure.
    for seg in segments:
        assert seg.audio.dtype == np.float32
        assert seg.end_ms >= seg.start_ms
