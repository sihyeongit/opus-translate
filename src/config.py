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
    max_segment_ms: int = 15000


@dataclass(frozen=True)
class AsrConfig:
    # faster-whisper model id (auto-downloaded from HF on first run).
    # Short English-only segments run at RTF 1.5-7x on Ryzen AI 9 HX 370.
    model_size: str = "small.en"
    device: str = "cpu"
    compute_type: str = "int8"
    language: str = "en"
    cpu_threads: int = 12
    num_workers: int = 2
    beam_size: int = 1


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
class OverlayConfig:
    font_family: str = "Pretendard"
    font_family_fallback: str = "Malgun Gothic"
    ko_font_size: int = 28
    en_font_size: int = 18
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
    overlay: OverlayConfig = field(default_factory=OverlayConfig)
    hotkey: HotkeyConfig = field(default_factory=HotkeyConfig)


CONFIG = AppConfig()
