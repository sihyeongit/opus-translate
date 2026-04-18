"""Silero VAD wrapper producing speech segments from a frame stream.

Emits contiguous speech segments bounded by silence gaps. Adds small
pre/post-roll to prevent clipping word onsets and trailing phonemes.
"""
from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
from typing import Iterable, Iterator, List

import numpy as np

log = logging.getLogger(__name__)


@dataclass
class SpeechSegment:
    audio: np.ndarray  # float32 mono 16kHz
    start_ms: int      # monotonic ms since stream start
    end_ms: int


class SileroVAD:
    """Streaming VAD that groups frames into SpeechSegment chunks.

    Silero v5 expects 512-sample (32ms @ 16kHz) chunks as float32 tensors.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        frame_ms: int = 32,
        threshold: float = 0.5,
        min_speech_ms: int = 300,
        min_silence_ms: int = 500,
        max_segment_ms: int = 15000,
        preroll_ms: int = 200,
        postroll_ms: int = 300,
    ):
        import torch
        from silero_vad import load_silero_vad

        self._torch = torch
        self._model = load_silero_vad()
        self._sr = sample_rate
        self._frame_samples = sample_rate * frame_ms // 1000
        self._threshold = threshold
        self._min_speech_frames = max(1, min_speech_ms // frame_ms)
        self._min_silence_frames = max(1, min_silence_ms // frame_ms)
        self._max_segment_frames = max_segment_ms // frame_ms
        self._preroll_frames = preroll_ms // frame_ms
        self._postroll_frames = postroll_ms // frame_ms
        self._frame_ms = frame_ms

        self._preroll: deque[np.ndarray] = deque(maxlen=self._preroll_frames)
        self._active: List[np.ndarray] = []
        self._active_start_frame = 0
        self._silence_run = 0
        self._speech_run = 0
        self._in_speech = False
        self._frame_idx = 0

    def _is_speech(self, frame: np.ndarray) -> bool:
        tensor = self._torch.from_numpy(frame)
        with self._torch.no_grad():
            prob = self._model(tensor, self._sr).item()
        return prob >= self._threshold

    def process(self, frames: Iterable[np.ndarray]) -> Iterator[SpeechSegment]:
        for frame in frames:
            if len(frame) != self._frame_samples:
                log.warning("Unexpected frame length %d (expected %d)",
                            len(frame), self._frame_samples)
                continue

            speech = self._is_speech(frame)
            self._frame_idx += 1

            if not self._in_speech:
                self._preroll.append(frame)
                if speech:
                    self._speech_run += 1
                    if self._speech_run >= 1:
                        self._in_speech = True
                        self._active = list(self._preroll)
                        self._active_start_frame = self._frame_idx - len(self._active)
                        self._silence_run = 0
                else:
                    self._speech_run = 0
                continue

            self._active.append(frame)
            if speech:
                self._silence_run = 0
            else:
                self._silence_run += 1

            segment_too_long = len(self._active) >= self._max_segment_frames
            silence_long_enough = self._silence_run >= self._min_silence_frames
            has_min_speech = len(self._active) - self._silence_run >= self._min_speech_frames

            if silence_long_enough and has_min_speech:
                yield self._flush()
            elif silence_long_enough and not has_min_speech:
                self._reset()
            elif segment_too_long:
                yield self._flush()

    def _flush(self) -> SpeechSegment:
        audio = np.concatenate(self._active).astype(np.float32)
        start_ms = self._active_start_frame * self._frame_ms
        end_ms = start_ms + int(len(audio) * 1000 / self._sr)
        seg = SpeechSegment(audio=audio, start_ms=start_ms, end_ms=end_ms)
        self._reset()
        return seg

    def _reset(self) -> None:
        self._in_speech = False
        self._active = []
        self._preroll.clear()
        self._silence_run = 0
        self._speech_run = 0
