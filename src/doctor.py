"""Runtime environment checks for Opus Translate.

Run with:
    python -m src.doctor
"""
from __future__ import annotations

import importlib.util
import platform
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .config import CONFIG


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    message: str


def _has_module(module: str) -> bool:
    return importlib.util.find_spec(module) is not None


def _check_python() -> CheckResult:
    version = sys.version_info
    ok = (3, 10) <= (version.major, version.minor) <= (3, 13)
    text = f"{platform.python_version()} ({sys.executable})"
    if ok:
        return CheckResult("Python", True, text)
    return CheckResult("Python", False, f"{text}; expected Python 3.10-3.13")


def _check_import(label: str, module: str) -> CheckResult:
    if _has_module(module):
        return CheckResult(label, True, f"`{module}` importable")
    return CheckResult(label, False, f"`{module}` is missing")


def _check_nllb_model() -> CheckResult:
    model_dir = CONFIG.mt.model_dir
    required = [
        model_dir / "model.bin",
        model_dir / "config.json",
        model_dir / "tokenizer.json",
        model_dir / "sentencepiece.bpe.model",
    ]
    missing = [path.name for path in required if not path.exists()]
    if not missing:
        return CheckResult("NLLB model", True, str(model_dir))
    return CheckResult(
        "NLLB model",
        False,
        f"{model_dir} missing: {', '.join(missing)}; run `python scripts\\setup_all.py`",
    )


def _check_loopback() -> CheckResult:
    if not _has_module("pyaudiowpatch"):
        return CheckResult("WASAPI loopback", False, "`pyaudiowpatch` is missing")
    try:
        import pyaudiowpatch as pyaudio

        from .audio_capture import find_default_loopback

        pa = pyaudio.PyAudio()
        try:
            device = find_default_loopback(pa)
        finally:
            pa.terminate()
    except Exception as exc:
        return CheckResult("WASAPI loopback", False, str(exc))
    return CheckResult(
        "WASAPI loopback",
        True,
        f"{device.name} @ {device.sample_rate}Hz ({device.channels}ch)",
    )


def _check_faster_whisper_cache() -> CheckResult:
    # faster-whisper downloads model weights through Hugging Face cache on first
    # real run. Avoid loading the model here because that is slow and can use GBs
    # of RAM; this check only reports the configured model id.
    if not _has_module("faster_whisper"):
        return CheckResult("ASR backend", False, "`faster_whisper` is missing")
    return CheckResult(
        "ASR backend",
        True,
        (
            "faster-whisper configured model: "
            f"{CONFIG.asr.model_size} ({CONFIG.asr.device}/{CONFIG.asr.compute_type})"
        ),
    )


def _asr_repo_id(model_size: str) -> str:
    if "/" in model_size:
        return model_size
    return f"Systran/faster-whisper-{model_size}"


def _check_asr_model_cache() -> CheckResult:
    model_size = CONFIG.asr.model_size
    if Path(model_size).exists():
        return CheckResult("ASR model cache", True, model_size)
    if not _has_module("huggingface_hub"):
        return CheckResult("ASR model cache", False, "`huggingface_hub` is missing")
    try:
        from huggingface_hub import try_to_load_from_cache

        repo_id = _asr_repo_id(model_size)
        cached_config = try_to_load_from_cache(repo_id, "config.json")
    except Exception as exc:
        return CheckResult("ASR model cache", False, str(exc))
    if isinstance(cached_config, str):
        return CheckResult("ASR model cache", True, str(cached_config))
    return CheckResult(
        "ASR model cache",
        False,
        f"{repo_id} is not cached; run `python scripts\\setup_all.py`",
    )


def _run_checks() -> list[CheckResult]:
    checks: list[Callable[[], CheckResult]] = [
        _check_python,
        lambda: _check_import("NumPy", "numpy"),
        lambda: _check_import("SciPy", "scipy"),
        lambda: _check_import("Silero VAD", "silero_vad"),
        _check_faster_whisper_cache,
        lambda: _check_import("Hugging Face Hub", "huggingface_hub"),
        _check_asr_model_cache,
        lambda: _check_import("CTranslate2", "ctranslate2"),
        lambda: _check_import("Transformers", "transformers"),
        lambda: _check_import("SentencePiece", "sentencepiece"),
        lambda: _check_import("PyQt6", "PyQt6"),
        lambda: _check_import("Keyboard hotkeys", "keyboard"),
        lambda: _check_import("PyWin32", "win32api"),
        _check_nllb_model,
        _check_loopback,
    ]
    return [check() for check in checks]


def main() -> int:
    print("Opus Translate environment check")
    print("=" * 34)
    results = _run_checks()
    for result in results:
        marker = "OK" if result.ok else "FAIL"
        print(f"[{marker:<4}] {result.name}: {result.message}")

    failures = [result for result in results if not result.ok]
    if failures:
        print()
        print(f"{len(failures)} check(s) failed.")
        return 1

    print()
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
