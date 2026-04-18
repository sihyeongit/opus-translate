"""Download whisper.cpp Windows Vulkan binary and the GGML model.

Fetches the latest whisper.cpp release zip and the quantized turbo model
from HuggingFace. Safe to re-run; skips files already present.
"""
from __future__ import annotations

import io
import logging
import sys
import zipfile
from pathlib import Path

import requests
from tqdm import tqdm

ROOT = Path(__file__).resolve().parent.parent
BIN_DIR = ROOT / "bin"
MODELS_DIR = ROOT / "models"

WHISPER_RELEASE = (
    "https://github.com/ggml-org/whisper.cpp/releases/latest/download/"
    "whisper-blas-bin-x64.zip"
)
MODEL_URL = (
    "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/"
    "ggml-large-v3-turbo-q5_0.bin"
)
MODEL_FALLBACK_URL = (
    "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/"
    "ggml-medium.en-q5_0.bin"
)

log = logging.getLogger("download_whisper")


def download(url: str, dest: Path) -> None:
    if dest.exists() and dest.stat().st_size > 0:
        log.info("Already present, skipping: %s", dest.name)
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    log.info("Downloading %s", url)
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        with dest.open("wb") as f, tqdm(
            total=total, unit="B", unit_scale=True, desc=dest.name
        ) as bar:
            for chunk in r.iter_content(chunk_size=1 << 15):
                if chunk:
                    f.write(chunk)
                    bar.update(len(chunk))


def download_and_extract_zip(url: str, target_dir: Path) -> None:
    cli = target_dir / "whisper-cli.exe"
    if cli.exists():
        log.info("whisper-cli.exe already present, skipping archive download")
        return
    target_dir.mkdir(parents=True, exist_ok=True)
    log.info("Downloading %s", url)
    r = requests.get(url, timeout=120)
    r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        for name in zf.namelist():
            if name.endswith((".exe", ".dll")):
                out = target_dir / Path(name).name
                with zf.open(name) as src, out.open("wb") as dst:
                    dst.write(src.read())
                log.info("Extracted: %s", out.name)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        download_and_extract_zip(WHISPER_RELEASE, BIN_DIR)
    except Exception:
        log.exception(
            "Failed to download whisper.cpp release. If this persists, "
            "grab a Windows release manually from "
            "https://github.com/ggml-org/whisper.cpp/releases and unzip "
            "whisper-cli.exe plus its DLLs into %s", BIN_DIR,
        )
        return 1

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    try:
        download(MODEL_URL, MODELS_DIR / "ggml-large-v3-turbo-q5_0.bin")
    except Exception:
        log.exception("Primary model download failed; trying medium.en fallback")
        download(MODEL_FALLBACK_URL, MODELS_DIR / "ggml-medium.en-q5_0.bin")

    log.info("Whisper setup complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
