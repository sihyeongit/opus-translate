"""WASAPI loopback capture for Windows system audio.

Uses PyAudioWPatch (a PyAudio fork with WASAPI loopback support) to tap
the default speaker output without requiring a virtual audio cable.
"""
from __future__ import annotations

import logging
import queue
import threading
from dataclasses import dataclass
from typing import Iterator, Optional

import numpy as np
import pyaudiowpatch as pyaudio
from scipy.signal import resample_poly

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class LoopbackDevice:
    index: int
    name: str
    sample_rate: int
    channels: int


def find_default_loopback(pa: pyaudio.PyAudio) -> LoopbackDevice:
    """Locate the loopback endpoint for the current default output device."""
    default_out = pa.get_default_wasapi_device(d_out=True)
    default_name = default_out["name"]

    for info in pa.get_loopback_device_info_generator():
        if default_name in info["name"]:
            return LoopbackDevice(
                index=info["index"],
                name=info["name"],
                sample_rate=int(info["defaultSampleRate"]),
                channels=int(info["maxInputChannels"]),
            )
    raise RuntimeError(f"No loopback endpoint found for output device '{default_name}'")


class LoopbackCapture:
    """Streams system audio as 16kHz mono float32 frames.

    Call start() to begin capture in a background thread. Use frames() to
    iterate resampled frames (default 32ms chunks for VAD consumption).
    """

    def __init__(self, target_sr: int = 16000, frame_ms: int = 32, max_queue: int = 128):
        self._target_sr = target_sr
        self._frame_samples = target_sr * frame_ms // 1000
        self._queue: queue.Queue[np.ndarray] = queue.Queue(maxsize=max_queue)
        self._stop = threading.Event()
        self._pa: Optional[pyaudio.PyAudio] = None
        self._stream: Optional[pyaudio.Stream] = None
        self._thread: Optional[threading.Thread] = None
        self._device: Optional[LoopbackDevice] = None
        self._residual = np.empty(0, dtype=np.float32)

    @property
    def device(self) -> Optional[LoopbackDevice]:
        return self._device

    def start(self) -> None:
        self._pa = pyaudio.PyAudio()
        self._device = find_default_loopback(self._pa)
        log.info("Loopback device: %s @ %dHz (%dch)",
                 self._device.name, self._device.sample_rate, self._device.channels)

        self._stream = self._pa.open(
            format=pyaudio.paFloat32,
            channels=self._device.channels,
            rate=self._device.sample_rate,
            input=True,
            input_device_index=self._device.index,
            frames_per_buffer=int(self._device.sample_rate * 0.02),  # 20ms source chunks
            stream_callback=self._callback,
        )
        self._stream.start_stream()

    def _callback(self, in_data, frame_count, time_info, status):
        if status:
            log.debug("Stream status flags: %s", status)
        raw = np.frombuffer(in_data, dtype=np.float32)
        if self._device.channels > 1:
            raw = raw.reshape(-1, self._device.channels).mean(axis=1)

        if self._device.sample_rate != self._target_sr:
            raw = resample_poly(raw, self._target_sr, self._device.sample_rate).astype(np.float32)

        buf = np.concatenate([self._residual, raw])
        n_full = len(buf) // self._frame_samples
        for i in range(n_full):
            chunk = buf[i * self._frame_samples:(i + 1) * self._frame_samples]
            try:
                self._queue.put_nowait(chunk.copy())
            except queue.Full:
                log.warning("Audio queue full, dropping frame")
        self._residual = buf[n_full * self._frame_samples:]
        return (None, pyaudio.paContinue)

    def frames(self) -> Iterator[np.ndarray]:
        """Yield 16kHz mono float32 frames (frame_ms each) until stop() is called."""
        while not self._stop.is_set():
            try:
                yield self._queue.get(timeout=0.2)
            except queue.Empty:
                continue

    def stop(self) -> None:
        self._stop.set()
        if self._stream is not None:
            try:
                self._stream.stop_stream()
                self._stream.close()
            except Exception:
                log.exception("Failed to close stream cleanly")
        if self._pa is not None:
            self._pa.terminate()


if __name__ == "__main__":
    import time
    logging.basicConfig(level=logging.INFO)
    cap = LoopbackCapture()
    cap.start()
    print(f"Capturing from: {cap.device}")
    t0 = time.time()
    rms_sum = 0.0
    n = 0
    try:
        for frame in cap.frames():
            rms_sum += float(np.sqrt(np.mean(frame ** 2)))
            n += 1
            if n % 31 == 0:
                print(f"[{time.time()-t0:5.1f}s] frames={n} avg_rms={rms_sum/n:.4f}")
            if time.time() - t0 > 10:
                break
    finally:
        cap.stop()
