"""Runtime configuration for opus-translate."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = ROOT / "models"
BIN_DIR = ROOT / "bin"
LOGS_DIR = ROOT / "logs"


@dataclass(frozen=True)
class AudioConfig:
    target_sample_rate: int = 16000
    capture_channels: int = 2
    frame_ms: int = 32
    preroll_ms: int = 200
    postroll_ms: int = 300


@dataclass(frozen=True)
class VadConfig:
    threshold: float = 0.5
    min_speech_ms: int = 300
    min_silence_ms: int = 300 #원래 500
    # 8s keeps ASR comfortably below realtime on the target CPU while reducing
    # the sentence damage caused by cutting dense speech every 5s.
    max_segment_ms: int = 8000


@dataclass(frozen=True)
class AsrConfig:
    # faster-whisper model id (auto-downloaded from HF on first run).
    # small.en measured at RTF ~6x realtime on Ryzen AI 9 HX 370 (int8, beam=1)
    # with large headroom, so we step up to medium.en for accuracy. medium is
    # ~3x slower than small → still ~2x realtime at beam=1. Keep beam=1 here:
    # combining medium.en with beam>=3 on CPU pushes RTF near 1.0 and risks
    # falling behind the media if any burst of dense speech arrives.
    model_size: str = "medium.en"
    device: str = "cpu"
    compute_type: str = "int8"
    language: str = "en"
    cpu_threads: int = 12
    num_workers: int = 2
    beam_size: int = 1
    # Real-time captions should not spend tens of seconds retrying ambiguous
    # audio with temperature fallbacks. Keep decoding deterministic and bounded.
    temperature: float = 0.0
    max_new_tokens: int = 96
    without_timestamps: bool = True
    # No initial_prompt. On medium.en CPU int8 each prompt token costs ~25ms of
    # decoder time; even a 14-token hint added ~350ms and pushed RTF over 1.0
    # (measured 5120-6621ms for 4992ms chunks). The domain-bias win is small
    # compared to the cost of falling behind realtime.
    initial_prompt: str = ""


@dataclass(frozen=True)
class TranslatorConfig:
    model_dir: Path = MODELS_DIR / "nllb-200-distilled-1.3B-ct2-int8"
    tokenizer_name: str = "facebook/nllb-200-distilled-1.3B"
    src_lang: str = "eng_Latn"
    tgt_lang: str = "kor_Hang"
    device: str = "cpu"
    compute_type: str = "int8"
    intra_threads: int = 8
    inter_threads: int = 1
    beam_size: int = 2
    context_window: int = 0


@dataclass(frozen=True)
class TranslationQualityConfig:
    # fast: lowest latency, balanced: default, quality: more context merging.
    profile: str = "balanced"
    merge_short_utterances: bool = True
    min_standalone_words: int = 5
    max_merge_words: int = 28
    max_hold_s: float = 1.6
    preserve_terms: tuple[str, ...] = (
        "API", "CPU", "GPU", "NPU", "GPT", "ChatGPT", "OpenAI", "Whisper",
        "NLLB", "Vulkan", "Windows", "YouTube", "Netflix", "Zoom", "Python",
        "JavaScript", "SQL", "GitHub",
    )
    phrase_fixes: tuple[tuple[str, str, str], ...] = (
        ("resident in memory", "모델 레지던트를 기억해야 합니다", "모델을 메모리에 상주시켜야 합니다"),
        ("resident in memory", "모형 거주자를 기억해야 합니다", "모델을 메모리에 상주시켜야 합니다"),
        ("keep the model resident", "모델 레지던트를 기억해야 합니다", "모델을 메모리에 상주시켜야 합니다"),
        ("falling behind the audio", "오디오 뒤에 떨어지지 않는", "오디오보다 뒤처지지 않는"),
    )


@dataclass(frozen=True)
class AsrSegmentMergeConfig:
    # fast: disabled, balanced: conservative merge, quality: stronger merge.
    profile: str = "balanced"
    enabled: bool = True
    short_segment_ms: int = 3500
    target_min_segment_ms: int = 3500
    max_hold_ms: int = 1200
    min_flush_segment_ms: int = 1200
    max_merged_segment_ms: int = 8000


@dataclass(frozen=True)
class OverlayConfig:
    font_family: str = "Pretendard"
    font_family_fallback: str = "Malgun Gothic"
    ko_font_size: int = 24
    en_font_size: int = 15
    max_lines: int = 2
    bottom_margin_px: int = 80
    width_ratio: float = 0.8
    fade_ms: int = 200


@dataclass(frozen=True)
class HotkeyConfig:
    toggle_visible: str = "ctrl+alt+t"
    cycle_lang_mode: str = "ctrl+alt+l"
    quit_app: str = "ctrl+alt+q"


@dataclass(frozen=True)
class AppConfig:
    audio: AudioConfig = field(default_factory=AudioConfig)
    vad: VadConfig = field(default_factory=VadConfig)
    asr: AsrConfig = field(default_factory=AsrConfig)
    mt: TranslatorConfig = field(default_factory=TranslatorConfig)
    quality: TranslationQualityConfig = field(default_factory=TranslationQualityConfig)
    segment_merge: AsrSegmentMergeConfig = field(default_factory=AsrSegmentMergeConfig)
    overlay: OverlayConfig = field(default_factory=OverlayConfig)
    hotkey: HotkeyConfig = field(default_factory=HotkeyConfig)


CONFIG = AppConfig()
