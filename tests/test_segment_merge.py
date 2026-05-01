from __future__ import annotations

import numpy as np

from src.config import AsrSegmentMergeConfig
from src.segment_merge import ShortAudioSegmentMerger
from src.vad import SpeechSegment


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance_ms(self, ms: int) -> None:
        self.now += ms / 1000


def segment(start_ms: int, end_ms: int) -> SpeechSegment:
    samples = max(1, (end_ms - start_ms) * 16)
    return SpeechSegment(
        audio=np.ones(samples, dtype=np.float32),
        start_ms=start_ms,
        end_ms=end_ms,
    )


def test_merges_two_short_segments():
    merger = ShortAudioSegmentMerger(AsrSegmentMergeConfig())

    assert merger.offer(segment(0, 2000)) == []
    ready = merger.offer(segment(2000, 4000))

    assert len(ready) == 1
    assert ready[0].start_ms == 0
    assert ready[0].end_ms == 4000
    assert ready[0].audio.dtype == np.float32


def test_keeps_collecting_if_merged_segment_is_still_too_short():
    merger = ShortAudioSegmentMerger(
        AsrSegmentMergeConfig(target_min_segment_ms=3500, max_merged_segment_ms=8000)
    )

    assert merger.offer(segment(0, 928)) == []
    assert merger.offer(segment(928, 2144)) == []
    ready = merger.offer(segment(2144, 4000))

    assert len(ready) == 1
    assert ready[0].start_ms == 0
    assert ready[0].end_ms == 4000


def test_flushes_pending_after_timeout():
    clock = FakeClock()
    merger = ShortAudioSegmentMerger(AsrSegmentMergeConfig(max_hold_ms=1200), now_fn=clock)

    assert merger.offer(segment(0, 2000)) == []
    clock.advance_ms(1199)
    assert merger.flush_stale() is None
    clock.advance_ms(1)
    flushed = merger.flush_stale()

    assert flushed is not None
    assert flushed.start_ms == 0
    assert flushed.end_ms == 2000


def test_drops_tiny_pending_after_timeout():
    clock = FakeClock()
    merger = ShortAudioSegmentMerger(
        AsrSegmentMergeConfig(max_hold_ms=1200, min_flush_segment_ms=1200),
        now_fn=clock,
    )

    assert merger.offer(segment(0, 672)) == []
    clock.advance_ms(1200)

    assert merger.flush_stale() is None
    assert merger.flush() is None


def test_tiny_pending_can_still_merge_with_next_segment():
    merger = ShortAudioSegmentMerger(
        AsrSegmentMergeConfig(min_flush_segment_ms=1200, max_merged_segment_ms=8000)
    )

    assert merger.offer(segment(0, 672)) == []
    ready = merger.offer(segment(672, 5000))

    assert len(ready) == 1
    assert ready[0].start_ms == 0
    assert ready[0].end_ms == 5000


def test_long_segment_passes_through_immediately():
    merger = ShortAudioSegmentMerger(AsrSegmentMergeConfig(short_segment_ms=3500))

    ready = merger.offer(segment(0, 6000))

    assert len(ready) == 1
    assert ready[0].start_ms == 0
    assert ready[0].end_ms == 6000


def test_does_not_merge_past_max_duration():
    merger = ShortAudioSegmentMerger(
        AsrSegmentMergeConfig(short_segment_ms=3500, max_merged_segment_ms=8000)
    )

    assert merger.offer(segment(0, 3000)) == []
    ready = merger.offer(segment(3000, 10000))

    assert len(ready) == 2
    assert ready[0].start_ms == 0
    assert ready[0].end_ms == 3000
    assert ready[1].start_ms == 3000
    assert ready[1].end_ms == 10000


def test_fast_profile_disables_merging():
    merger = ShortAudioSegmentMerger(AsrSegmentMergeConfig(profile="fast"))

    ready = merger.offer(segment(0, 2000))

    assert len(ready) == 1
    assert ready[0].start_ms == 0
    assert ready[0].end_ms == 2000
