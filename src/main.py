"""Opus Translate entry point.

Wires audio capture → VAD → Whisper ASR → NLLB translator → PyQt overlay.
Each stage after capture runs in its own worker thread with bounded
queues so back-pressure cannot starve the audio callback.
"""
from __future__ import annotations

import logging
import queue
import signal
import sys
import threading
import time
from dataclasses import dataclass
from typing import Optional

import numpy as np

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from .asr import FasterWhisperASR
from .audio_capture import LoopbackCapture
from .config import CONFIG
from .overlay import SubtitleOverlay
from .translator import NLLBTranslator
from .vad import SileroVAD, SpeechSegment

log = logging.getLogger(__name__)


@dataclass
class TranscribedSegment:
    en: str
    start_ms: int
    end_ms: int
    seg_ms: int = 0
    asr_ms: int = 0


class Pipeline:
    def __init__(self, overlay: SubtitleOverlay):
        self.overlay = overlay
        self.capture = LoopbackCapture(
            target_sr=CONFIG.audio.target_sample_rate,
            frame_ms=CONFIG.audio.frame_ms,
        )
        self.vad = SileroVAD(
            sample_rate=CONFIG.audio.target_sample_rate,
            frame_ms=CONFIG.audio.frame_ms,
            threshold=CONFIG.vad.threshold,
            min_speech_ms=CONFIG.vad.min_speech_ms,
            min_silence_ms=CONFIG.vad.min_silence_ms,
            max_segment_ms=CONFIG.vad.max_segment_ms,
            preroll_ms=CONFIG.audio.preroll_ms,
            postroll_ms=CONFIG.audio.postroll_ms,
        )
        self.asr = FasterWhisperASR(
            model_size=CONFIG.asr.model_size,
            device=CONFIG.asr.device,
            compute_type=CONFIG.asr.compute_type,
            cpu_threads=CONFIG.asr.cpu_threads,
            num_workers=CONFIG.asr.num_workers,
            beam_size=CONFIG.asr.beam_size,
            language=CONFIG.asr.language,
        )
        self.asr.warm_up()
        self.translator = NLLBTranslator(
            model_dir=CONFIG.mt.model_dir,
            tokenizer_name=CONFIG.mt.tokenizer_name,
            src_lang=CONFIG.mt.src_lang,
            tgt_lang=CONFIG.mt.tgt_lang,
            device=CONFIG.mt.device,
            compute_type=CONFIG.mt.compute_type,
            intra_threads=CONFIG.mt.intra_threads,
            inter_threads=CONFIG.mt.inter_threads,
            beam_size=CONFIG.mt.beam_size,
            context_window=CONFIG.mt.context_window,
        )

        self._asr_q: queue.Queue[SpeechSegment] = queue.Queue(maxsize=16)
        self._mt_q: queue.Queue[TranscribedSegment] = queue.Queue(maxsize=16)
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []

    def start(self) -> None:
        self.capture.start()
        self._threads = [
            threading.Thread(target=self._vad_loop, name="vad", daemon=True),
            threading.Thread(target=self._asr_loop, name="asr", daemon=True),
            threading.Thread(target=self._mt_loop, name="mt", daemon=True),
        ]
        for t in self._threads:
            t.start()
        log.info("Pipeline started")

    def stop(self) -> None:
        log.info("Stopping pipeline")
        self._stop.set()
        self.capture.stop()

    def _vad_loop(self) -> None:
        try:
            for segment in self.vad.process(self.capture.frames()):
                if self._stop.is_set():
                    return
                try:
                    self._asr_q.put(segment, timeout=1.0)
                except queue.Full:
                    log.warning("ASR queue full; dropping speech segment (%dms)",
                                segment.end_ms - segment.start_ms)
        except Exception:
            log.exception("VAD loop crashed")

    def _asr_loop(self) -> None:
        while not self._stop.is_set():
            try:
                segment = self._asr_q.get(timeout=0.5)
            except queue.Empty:
                continue
            seg_ms = segment.end_ms - segment.start_ms
            t0 = time.time()
            try:
                text = self.asr.transcribe(segment.audio)
            except Exception:
                log.exception("ASR failed")
                continue
            asr_ms = int((time.time() - t0) * 1000)
            text = text.strip()
            if not text or _is_noise(text):
                continue
            if asr_ms > seg_ms:
                log.warning("ASR slower than realtime: seg=%dms, asr=%dms (backlog=%d)",
                            seg_ms, asr_ms, self._asr_q.qsize())
            try:
                self._mt_q.put(
                    TranscribedSegment(en=text, start_ms=segment.start_ms, end_ms=segment.end_ms,
                                       seg_ms=seg_ms, asr_ms=asr_ms),
                    timeout=1.0,
                )
            except queue.Full:
                log.warning("MT queue full; dropping transcription")

    def _mt_loop(self) -> None:
        while not self._stop.is_set():
            try:
                item = self._mt_q.get(timeout=0.5)
            except queue.Empty:
                continue
            t0 = time.time()
            try:
                ko = self.translator.translate(item.en)
            except Exception:
                log.exception("Translation failed")
                continue
            mt_ms = int((time.time() - t0) * 1000)
            if ko:
                self.overlay.push_caption(en=item.en, ko=ko)
                log.info("seg=%dms asr=%dms mt=%dms | EN: %s | KO: %s",
                         item.seg_ms, item.asr_ms, mt_ms, item.en, ko)


_NOISE_TOKENS = {"[music]", "[silence]", "(music)", "(silence)", ".", ",", "..."}


def _is_noise(text: str) -> bool:
    return text.strip().lower() in _NOISE_TOKENS


def _install_hotkeys(overlay: SubtitleOverlay, app: QApplication) -> None:
    try:
        import keyboard
    except ImportError:
        log.warning("`keyboard` unavailable; global hotkeys disabled")
        return

    def run_on_qt(fn):
        QTimer.singleShot(0, fn)

    keyboard.add_hotkey(CONFIG.hotkey.toggle_visible,
                        lambda: run_on_qt(overlay.toggle_visible))
    keyboard.add_hotkey(CONFIG.hotkey.cycle_lang_mode,
                        lambda: run_on_qt(overlay.cycle_lang_mode))
    keyboard.add_hotkey(CONFIG.hotkey.quit_app,
                        lambda: run_on_qt(app.quit))


def main() -> int:
    # Windows consoles often default to cp949; force UTF-8 so KO logs render.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )

    app = QApplication(sys.argv)
    overlay = SubtitleOverlay(
        font_family=CONFIG.overlay.font_family_fallback,
        ko_font_size=CONFIG.overlay.ko_font_size,
        en_font_size=CONFIG.overlay.en_font_size,
        bottom_margin_px=CONFIG.overlay.bottom_margin_px,
        width_ratio=CONFIG.overlay.width_ratio,
        max_captions=CONFIG.overlay.max_lines,
    )
    overlay.show()
    overlay.push_caption(en="Opus Translate ready.", ko="오퍼스 트랜슬레이트 준비 완료.")

    pipeline = Pipeline(overlay)
    pipeline.start()

    _install_hotkeys(overlay, app)

    signal.signal(signal.SIGINT, lambda *_: app.quit())

    try:
        return app.exec()
    finally:
        pipeline.stop()


if __name__ == "__main__":
    raise SystemExit(main())
