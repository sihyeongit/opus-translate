"""ASR backend using faster-whisper (CTranslate2 in-process).

Keeps the model resident in RAM so there is zero per-segment startup
cost. Earlier we shelled out to whisper-cli.exe, but each subprocess
call had to reload the 574MB GGML model from disk (~1–2s overhead on
every utterance), which caused the pipeline to fall behind media that
emits a sentence every ~2 seconds.
"""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np

log = logging.getLogger(__name__)


class FasterWhisperASR:
    def __init__(
        self,
        model_size: str = "small.en",
        device: str = "cpu",
        compute_type: str = "int8",
        cpu_threads: int = 12,
        num_workers: int = 2,
        beam_size: int = 1,
        language: str = "en",
        download_root: Optional[str] = None,
    ):
        from faster_whisper import WhisperModel

        log.info(
            "Loading faster-whisper '%s' (%s/%s, threads=%d)",
            model_size, device, compute_type, cpu_threads,
        )
        self._model = WhisperModel(
            model_size,
            device=device,
            compute_type=compute_type,
            cpu_threads=cpu_threads,
            num_workers=num_workers,
            download_root=download_root,
        )
        self._beam_size = beam_size
        self._language = language
        log.info("faster-whisper model ready (resident)")

    def warm_up(self) -> None:
        """Run a tiny dummy inference so the first real call is fast."""
        dummy = np.zeros(16000, dtype=np.float32)
        list(self._model.transcribe(
            dummy, language=self._language, beam_size=1, vad_filter=False,
        )[0])

    def transcribe(self, audio: np.ndarray, sample_rate: int = 16000) -> str:
        if sample_rate != 16000:
            raise ValueError(f"expected 16kHz audio, got {sample_rate}")
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)

        try:
            segments, _info = self._model.transcribe(
                audio,
                language=self._language,
                beam_size=self._beam_size,
                vad_filter=False,  # we do our own VAD upstream
                condition_on_previous_text=False,
                no_speech_threshold=0.6,
                log_progress=False,
            )
            text = " ".join(seg.text for seg in segments).strip()
        except Exception:
            log.exception("faster-whisper transcribe failed")
            return ""

        return text
