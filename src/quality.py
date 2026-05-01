"""Translation quality helpers.

These helpers sit around the MT model rather than inside it. They keep latency
bounded while giving NLLB cleaner source text and less awkward Korean output.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, replace
from difflib import SequenceMatcher

from .config import TranslationQualityConfig


@dataclass(frozen=True)
class QualityUtterance:
    text: str
    start_ms: int
    end_ms: int
    seg_ms: int = 0
    asr_ms: int = 0


class TranslationQualityProcessor:
    def __init__(self, config: TranslationQualityConfig):
        self.config = _profiled_config(config)
        self._pending: QualityUtterance | None = None
        self._pending_t = 0.0
        self._term_fixes = _term_fixes(self.config.preserve_terms)

    def offer_utterance(self, item: QualityUtterance) -> list[QualityUtterance]:
        """Return utterances ready for MT, holding short context-poor snippets."""
        item = replace(item, text=normalize_source_text(item.text))
        if not item.text:
            return []

        if not self.config.merge_short_utterances:
            return [item]

        if self._pending is not None:
            merged = _merge_utterances(self._pending, item)
            self._pending = None
            return [merged]

        if self._should_hold(item.text):
            self._pending = item
            self._pending_t = time.time()
            return []

        return [item]

    def flush_stale(self) -> QualityUtterance | None:
        if self._pending is None:
            return None
        if (time.time() - self._pending_t) < self.config.max_hold_s:
            return None
        item = self._pending
        self._pending = None
        return item

    def postprocess_ko(self, source_en: str, ko: str) -> str:
        ko = normalize_korean_subtitle(ko)
        ko = remove_repeated_sentences(ko)
        ko = self._apply_phrase_fixes(source_en, ko)
        ko = self._preserve_source_terms(source_en, ko)
        return ko.strip()

    def _should_hold(self, text: str) -> bool:
        words = _words(text)
        if not words:
            return False
        if len(words) >= self.config.min_standalone_words:
            return False
        if len(words) > self.config.max_merge_words:
            return False

        first = words[0].lower().strip("'\"")
        if first in _CONTEXT_DEPENDENT_STARTERS:
            return True
        return len(words) <= 3

    def _preserve_source_terms(self, source_en: str, ko: str) -> str:
        source_lower = source_en.lower()
        out = ko
        for term, variants in self._term_fixes.items():
            if term.lower() not in source_lower:
                continue
            if term.lower() in out.lower():
                continue
            for variant in variants:
                out = re.sub(variant, term, out, flags=re.IGNORECASE)
        return out

    def _apply_phrase_fixes(self, source_en: str, ko: str) -> str:
        source_lower = source_en.lower()
        out = ko
        for source_phrase, bad_ko, fixed_ko in self.config.phrase_fixes:
            if source_phrase.lower() not in source_lower:
                continue
            out = out.replace(bad_ko, fixed_ko)
        return out


def normalize_source_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,.?!;:])", r"\1", text)
    text = re.sub(r"([({\[])\s+", r"\1", text)
    text = re.sub(r"\s+([)}\]])", r"\1", text)
    return text


def normalize_korean_subtitle(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,.?!;:])", r"\1", text)
    text = re.sub(r"([({\[])\s+", r"\1", text)
    text = re.sub(r"\s+([)}\]])", r"\1", text)
    text = text.replace(" ,", ",").replace(" .", ".")
    return text


def remove_repeated_sentences(text: str) -> str:
    pieces = _split_korean_sentences(text)
    if len(pieces) <= 1:
        return text

    out: list[str] = []
    for piece in pieces:
        normalized = _normalize_for_repeat(piece)
        if out:
            prev = _normalize_for_repeat(out[-1])
            if normalized == prev:
                continue
            if SequenceMatcher(None, normalized, prev).ratio() > 0.92:
                continue
        out.append(piece)
    return " ".join(out).strip()


def _profiled_config(config: TranslationQualityConfig) -> TranslationQualityConfig:
    profile = config.profile.lower().strip()
    if profile == "fast":
        return replace(config, merge_short_utterances=False)
    if profile == "quality":
        return replace(config, min_standalone_words=6, max_hold_s=max(config.max_hold_s, 2.4))
    return config


def _merge_utterances(left: QualityUtterance, right: QualityUtterance) -> QualityUtterance:
    text = normalize_source_text(f"{left.text} {right.text}")
    return QualityUtterance(
        text=text,
        start_ms=left.start_ms,
        end_ms=right.end_ms,
        seg_ms=max(0, right.end_ms - left.start_ms),
        asr_ms=left.asr_ms + right.asr_ms,
    )


def _words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9']+", text)


def _split_korean_sentences(text: str) -> list[str]:
    matches = re.findall(r"[^.!?。！？]+[.!?。！？]?", text)
    return [piece.strip() for piece in matches if piece.strip()]


def _normalize_for_repeat(text: str) -> str:
    return re.sub(r"\W+", "", text.lower())


def _term_fixes(terms: tuple[str, ...]) -> dict[str, tuple[str, ...]]:
    known = {
        "Windows": (r"윈도우즈?",),
        "YouTube": (r"유튜브",),
        "Netflix": (r"넷플릭스",),
        "Zoom": (r"줌",),
        "Python": (r"파이썬",),
        "JavaScript": (r"자바스크립트",),
        "GitHub": (r"깃허브",),
        "OpenAI": (r"오픈\s*AI", r"오픈에이아이"),
        "ChatGPT": (r"챗\s*GPT", r"챗지피티"),
        "Whisper": (r"위스퍼",),
        "Vulkan": (r"불칸", r"벌칸"),
    }
    return {term: known[term] for term in terms if term in known}


_CONTEXT_DEPENDENT_STARTERS = {
    "it", "it's", "its", "that", "that's", "this", "these", "those", "they",
    "they're", "we", "we're", "you", "you're", "he", "she", "so", "but", "and",
    "because", "then", "now", "also", "which", "who", "what", "why", "how",
    "yes", "no", "right", "exactly", "absolutely", "sure", "okay", "well",
}
