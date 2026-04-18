"""One-shot setup: whisper.cpp binary + GGML model + NLLB CT2 conversion."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import download_whisper
import setup_nllb


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    rc = download_whisper.main()
    if rc != 0:
        return rc
    return setup_nllb.main()


if __name__ == "__main__":
    sys.exit(main())
