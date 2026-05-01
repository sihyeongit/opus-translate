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
        initial_prompt: str = "",
        temperature: float = 0.0,
        max_new_tokens: int = 96,
        without_timestamps: bool = True,
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
        self._initial_prompt = initial_prompt or ""
        self._temperature = temperature
        self._max_new_tokens = max_new_tokens
        self._without_timestamps = without_timestamps
        log.info("faster-whisper model ready (resident)")

    def warm_up(self) -> None:
        """Run a tiny dummy inference so the first real call is fast."""
        dummy = np.zeros(16000, dtype=np.float32)
        list(self._model.transcribe(
            dummy, language=self._language, beam_size=1, vad_filter=False,
        )[0])

    def transcribe(self, audio: np.ndarray, sample_rate: int = 16000) -> list[str]:
        """Return one string per whisper sub-segment (≈ one sentence each).

        Emitting sub-segments individually lets the caller push each sentence
        to the translator independently, so subtitles stream at the speaker's
        sentence pace instead of appearing as one long burst per VAD chunk.
        """
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
                # condition_on_previous_text only matters for >30s audio
                # (multi-window chunking). Our chunks are always ~5s, so leaving
                # it False avoids any implicit state while costing nothing.
                condition_on_previous_text=False,
                initial_prompt=self._initial_prompt or None,
                temperature=self._temperature,
                max_new_tokens=self._max_new_tokens,
                without_timestamps=self._without_timestamps,
                no_speech_threshold=0.6,
                log_progress=False,
            )
            out: list[str] = []
            for seg in segments:
                for sentence in _split_sentences(seg.text):
                    if sentence:
                        out.append(sentence)
            return _merge_short_fragments(out)
        except Exception:
            log.exception("faster-whisper transcribe failed")
            return []


_SENTENCE_END = ".?!"
_MIN_WORDS = 4  # fragments shorter than this are merged with the next sentence


def _merge_short_fragments(sentences: list[str]) -> list[str]:
    """Merge sub-4-word fragments into the following sentence.

    Whisper sometimes emits very short segments like "Absolutely." or "Right."
    as standalone lines. On their own they translate poorly (no context) and
    clutter the overlay. Appending them to the next sentence gives NLLB enough
    context to choose the right register ("그렇습니다" vs "맞아요" etc.).
    """
    if not sentences:
        return sentences
    out: list[str] = []
    pending = ""
    for sent in sentences:
        combined = (pending + " " + sent).strip() if pending else sent
        if len(combined.split()) < _MIN_WORDS and sent is not sentences[-1]:
            pending = combined
        else:
            out.append(combined)
            pending = ""
    if pending:
        if out:
            out[-1] = out[-1] + " " + pending
        else:
            out.append(pending)
    return out


def _split_sentences(text: str) -> list[str]:
    """Split whisper text into sentences on .?! while keeping the punctuation.

    Whisper usually yields one sentence per sub-segment, but occasionally packs
    two or three together ("Absolutely. Does it create..."). Splitting here
    keeps each caption to a single sentence without losing terminal punctuation.
    """
    text = text.strip()
    if not text:
        return []
    out: list[str] = []
    buf: list[str] = []
    for ch in text:
        buf.append(ch)
        if ch in _SENTENCE_END:
            piece = "".join(buf).strip()
            if piece:
                out.append(piece)
            buf = []
    tail = "".join(buf).strip()
    if tail:
        out.append(tail)
    return out
