"""One-shot setup for the current runtime path."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import setup_asr
import setup_nllb


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    rc = setup_asr.main()
    if rc != 0:
        return rc
    return setup_nllb.main()


if __name__ == "__main__":
    sys.exit(main())
