"""Merge short VAD segments before ASR.

Whisper has a noticeable fixed cost per call. Very short audio chunks can be
slower than realtime even when longer chunks are comfortably faster, so this
module optionally holds one short VAD segment and merges it with the next one.
"""
from __future__ import annotations

import logging
import time
from dataclasses import replace
from typing import Callable

import numpy as np

from .config import AsrSegmentMergeConfig
from .vad import SpeechSegment

log = logging.getLogger(__name__)


class ShortAudioSegmentMerger:
    def __init__(
        self,
        config: AsrSegmentMergeConfig,
        now_fn: Callable[[], float] | None = None,
    ):
        self.config = _profiled_config(config)
        self._now = now_fn or time.monotonic
        self._pending: SpeechSegment | None = None
        self._pending_t = 0.0

    def offer(self, segment: SpeechSegment) -> list[SpeechSegment]:
        if not self.config.enabled:
            return [segment]

        ready: list[SpeechSegment] = []

        stale = self.flush_stale()
        if stale is not None:
            ready.append(stale)

        if self._pending is None:
            if self._should_hold(segment):
                self._hold(segment)
                return ready
            ready.append(segment)
            return ready

        if self._can_merge(self._pending, segment):
            left = self._pending
            merged = _merge_segments(left, segment)
            log.info(
                "merged short ASR segments: %dms + %dms = %dms",
                _duration_ms(left),
                _duration_ms(segment),
                _duration_ms(merged),
            )
            self._pending = None
            if self._should_keep_collecting(merged):
                self._hold(merged, reset_timer=False)
                log.info(
                    "holding merged ASR segment until target duration: %dms (target=%dms)",
                    _duration_ms(merged),
                    self.config.target_min_segment_ms,
                )
                return ready
            ready.append(merged)
            return ready

        ready.append(self._pending)
        self._pending = None
        if self._should_hold(segment):
            self._hold(segment)
        else:
            ready.append(segment)
        return ready

    def flush_stale(self) -> SpeechSegment | None:
        if self._pending is None:
            return None
        elapsed_ms = int((self._now() - self._pending_t) * 1000)
        if elapsed_ms < self.config.max_hold_ms:
            return None
        segment = self._pending
        self._pending = None
        duration_ms = _duration_ms(segment)
        if duration_ms < self.config.min_flush_segment_ms:
            log.info(
                "dropped tiny ASR segment after hold: %dms (min=%dms)",
                duration_ms,
                self.config.min_flush_segment_ms,
            )
            return None
        log.info("flushed short ASR segment after hold: %dms", _duration_ms(segment))
        return segment

    def flush(self) -> SpeechSegment | None:
        segment = self._pending
        self._pending = None
        return segment

    def _hold(self, segment: SpeechSegment, reset_timer: bool = True) -> None:
        self._pending = segment
        if reset_timer:
            self._pending_t = self._now()

    def _should_hold(self, segment: SpeechSegment) -> bool:
        return _duration_ms(segment) < self.config.short_segment_ms

    def _can_merge(self, left: SpeechSegment, right: SpeechSegment) -> bool:
        return (_duration_ms(left) + _duration_ms(right)) <= self.config.max_merged_segment_ms

    def _should_keep_collecting(self, segment: SpeechSegment) -> bool:
        return _duration_ms(segment) < self.config.target_min_segment_ms


def _profiled_config(config: AsrSegmentMergeConfig) -> AsrSegmentMergeConfig:
    profile = config.profile.lower().strip()
    if profile == "fast":
        return replace(config, enabled=False)
    if profile == "quality":
        return replace(
            config,
            short_segment_ms=max(config.short_segment_ms, 4500),
            target_min_segment_ms=max(config.target_min_segment_ms, 4500),
            max_hold_ms=max(config.max_hold_ms, 2000),
            max_merged_segment_ms=max(config.max_merged_segment_ms, 10000),
        )
    return config


def _merge_segments(left: SpeechSegment, right: SpeechSegment) -> SpeechSegment:
    return SpeechSegment(
        audio=np.concatenate([left.audio, right.audio]).astype(np.float32),
        start_ms=left.start_ms,
        end_ms=right.end_ms,
    )


def _duration_ms(segment: SpeechSegment) -> int:
    return segment.end_ms - segment.start_ms
