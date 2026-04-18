"""Download NLLB-200-distilled-1.3B and convert to CTranslate2 int8.

Uses the ct2-transformers-converter CLI shipped with ctranslate2. Output
lives under models/nllb-200-distilled-1.3B-ct2-int8/ alongside the HF
tokenizer files needed at runtime.
"""
from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = ROOT / "models"

HF_NAME = "facebook/nllb-200-distilled-1.3B"
OUTPUT_DIR = MODELS_DIR / "nllb-200-distilled-1.3B-ct2-int8"

log = logging.getLogger("setup_nllb")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if (OUTPUT_DIR / "model.bin").exists():
        log.info("NLLB CT2 model already exists at %s", OUTPUT_DIR)
        return 0

    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable, "-m", "ctranslate2.converters.transformers",
        "--model", HF_NAME,
        "--output_dir", str(OUTPUT_DIR),
        "--quantization", "int8",
        "--copy_files", "tokenizer.json", "sentencepiece.bpe.model",
        "special_tokens_map.json", "tokenizer_config.json",
    ]
    log.info("Running: %s", " ".join(cmd))
    proc = subprocess.run(cmd)
    if proc.returncode != 0:
        log.error("Conversion failed (rc=%d)", proc.returncode)
        return proc.returncode

    log.info("NLLB ready at %s", OUTPUT_DIR)
    return 0


if __name__ == "__main__":
    sys.exit(main())
