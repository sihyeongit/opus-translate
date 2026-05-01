from __future__ import annotations

from src.config import TranslationQualityConfig
from src.quality import (
    QualityUtterance,
    TranslationQualityProcessor,
    normalize_source_text,
    remove_repeated_sentences,
)


def test_normalize_source_text_removes_punctuation_spacing():
    assert normalize_source_text(" Hello   world  ! ") == "Hello world!"


def test_short_utterance_is_merged_with_next_sentence():
    processor = TranslationQualityProcessor(TranslationQualityConfig())

    first = QualityUtterance(text="That's why.", start_ms=0, end_ms=900, seg_ms=900, asr_ms=100)
    second = QualityUtterance(
        text="We need to keep the model resident.",
        start_ms=900,
        end_ms=3000,
        seg_ms=2100,
        asr_ms=300,
    )

    assert processor.offer_utterance(first) == []
    ready = processor.offer_utterance(second)

    assert len(ready) == 1
    assert ready[0].text == "That's why. We need to keep the model resident."
    assert ready[0].start_ms == 0
    assert ready[0].end_ms == 3000


def test_fast_profile_does_not_hold_short_utterances():
    processor = TranslationQualityProcessor(TranslationQualityConfig(profile="fast"))
    ready = processor.offer_utterance(
        QualityUtterance(text="Right.", start_ms=0, end_ms=500, seg_ms=500, asr_ms=100)
    )

    assert [item.text for item in ready] == ["Right."]


def test_remove_repeated_korean_sentences():
    text = "이것은 테스트입니다. 이것은 테스트입니다. 다음 문장입니다."
    assert remove_repeated_sentences(text) == "이것은 테스트입니다. 다음 문장입니다."


def test_postprocess_preserves_known_source_terms():
    processor = TranslationQualityProcessor(TranslationQualityConfig())
    ko = processor.postprocess_ko("OpenAI released this for Windows.", "오픈AI는 윈도우용으로 출시했습니다.")

    assert "OpenAI" in ko
    assert "Windows" in ko


def test_postprocess_applies_phrase_fixes():
    processor = TranslationQualityProcessor(TranslationQualityConfig())
    ko = processor.postprocess_ko(
        "That's why we need to keep the model resident in memory.",
        "그래서 우리는 모델 레지던트를 기억해야 합니다.",
    )

    assert ko == "그래서 우리는 모델을 메모리에 상주시켜야 합니다."
