"""Pre-download the faster-whisper ASR model into the Hugging Face cache."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from huggingface_hub import snapshot_download

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config import CONFIG

log = logging.getLogger("setup_asr")


def _repo_id(model_size: str) -> str:
    if "/" in model_size:
        return model_size
    return f"Systran/faster-whisper-{model_size}"


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    repo_id = _repo_id(CONFIG.asr.model_size)
    try:
        log.info("Downloading faster-whisper model cache: %s", repo_id)
        path = snapshot_download(repo_id=repo_id)
    except Exception:
        log.exception("Failed to download faster-whisper model: %s", repo_id)
        return 1
    log.info("ASR model ready at %s", path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
