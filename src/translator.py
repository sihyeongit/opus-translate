"""CTranslate2 NLLB-200 translator for English → Korean.

Int8 quantization keeps the 1.3B distilled model at ~1.5GB RAM with good
quality. Each utterance is translated independently: NLLB has no native
context-carryover mechanism, and concatenating source sentences causes
the decoder to reproduce earlier translations in the output.
"""
from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger(__name__)


class NLLBTranslator:
    def __init__(
        self,
        model_dir: Path,
        tokenizer_name: str,
        src_lang: str = "eng_Latn",
        tgt_lang: str = "kor_Hang",
        device: str = "cpu",
        compute_type: str = "int8",
        intra_threads: int = 8,
        inter_threads: int = 1,
        beam_size: int = 2,
        context_window: int = 0,  # kept for API stability, unused
    ):
        import ctranslate2
        from transformers import AutoTokenizer

        if not model_dir.exists():
            raise FileNotFoundError(f"CT2 model dir not found: {model_dir}")

        log.info("Loading NLLB CT2 model from %s (%s/%s)", model_dir, device, compute_type)
        self._model = ctranslate2.Translator(
            str(model_dir),
            device=device,
            compute_type=compute_type,
            intra_threads=intra_threads,
            inter_threads=inter_threads,
        )
        self._tokenizer = AutoTokenizer.from_pretrained(tokenizer_name, src_lang=src_lang)
        self._src_lang = src_lang
        self._tgt_lang = tgt_lang
        self._beam_size = beam_size

    def translate(self, text: str) -> str:
        """Translate *text* from English to Korean.

        Per-sentence, stateless. We tried feeding previous src/tgt as encoder
        context + forced target_prefix, but NLLB (not trained for multi-sentence
        inputs with prefixes) re-translated content that was dropped from the
        prev translation, producing duplicated phrases ("기억이 나지 않습니다."
        → next output: "확실히 내 인생에서. 시간, 이렇게 많은 위험."). The
        approach also doubled MT cost and contended with Whisper on CPU.
        """
        text = text.strip()
        if not text:
            return ""

        tokens = self._tokenizer.convert_ids_to_tokens(self._tokenizer.encode(text))

        results = self._model.translate_batch(
            [tokens],
            target_prefix=[[self._tgt_lang]],
            beam_size=self._beam_size,
            max_decoding_length=256,
        )
        hyp_tokens = results[0].hypotheses[0]
        if hyp_tokens and hyp_tokens[0] == self._tgt_lang:
            hyp_tokens = hyp_tokens[1:]

        ids = self._tokenizer.convert_tokens_to_ids(hyp_tokens)
        return self._tokenizer.decode(ids, skip_special_tokens=True).strip()
