# Opus Translate

PC 내부 오디오를 실시간으로 캡처해 **영어 → 한국어**로 번역·자막 표시하는 오프라인 데스크탑 도구.

유튜브, 넷플릭스, 온라인 강의, 팟캐스트 등 모든 시스템 사운드에 적용됩니다. 유료 서비스 없이 로컬에서 동작하며, 비용은 0원입니다.

---

## 주요 특징

- **완전 오프라인 / 무료** — 외부 API 호출 없음, 오픈소스 모델·런타임만 사용
- **고품질 번역** — OpenAI Whisper `large-v3-turbo` + Meta NLLB-200 조합
- **하드웨어 가속** — AMD Radeon iGPU(Vulkan) 기반 Whisper 추론
- **투명 오버레이 자막** — 영상 위에 덧붙는 항상-위, 클릭-통과 UI
- **듀얼 언어 표시** — 영어 원문 + 한국어 번역 동시 (핫키로 전환)
- **WASAPI 네이티브** — 가상 오디오 케이블(VB-Cable) 설치 불필요

---

## 대상 하드웨어

본 프로젝트는 다음 스펙 기준으로 최적화되어 있습니다.

| 구성 | 사양 |
|---|---|
| 모델 | ASUS Vivobook S14 (예시) |
| CPU | AMD Ryzen AI 9 HX 370 (12C/24T) |
| NPU | XDNA2 · 50 TOPS *(v1에서는 미사용, v2 확장 예정)* |
| iGPU | AMD Radeon 890M (RDNA 3.5) — **Whisper Vulkan 가속** |
| RAM | 24GB LPDDR5X 7500 MT/s |
| OS | Windows 11 |

다른 AMD/Intel 노트북에서도 Vulkan 드라이버만 있으면 동작하며, Vulkan 미지원 시 자동으로 CPU 모드로 전환됩니다.

---

## 아키텍처 개요

```
 ┌─────────────────────┐     ┌──────────────┐     ┌──────────────────────┐
 │ WASAPI Loopback     │────▶│ Silero VAD   │────▶│ Whisper large-v3-    │
 │ (PyAudioWPatch)     │     │ (발화 감지)   │     │ turbo · Vulkan iGPU  │
 └─────────────────────┘     └──────────────┘     └──────────────────────┘
                                                               │
                                                               ▼
 ┌──────────────────────┐    ┌──────────────────────────────────────────┐
 │ PyQt6 투명 오버레이   │◀───│ NLLB-200-distilled-1.3B · CTranslate2   │
 │ (EN + KO 자막)       │    │ (int8 · CPU 추론)                        │
 └──────────────────────┘    └──────────────────────────────────────────┘
```

**자원 배분**:
- CPU: 오디오 I/O, VAD, 번역 (NLLB)
- iGPU(Vulkan): Whisper ASR (지배적 연산)
- NPU: v1에서는 유휴 — 배터리/발열 여유 확보

상세 설계는 `C:\Users\LSH\.claude\plans\pc-purring-clarke.md` 참고.

---

## 폴더 구조

```
opus-translate/
├── src/                  # 애플리케이션 소스
│   ├── main.py           # 엔트리포인트 · 파이프라인 조립
│   ├── config.py         # 경로, 핫키, 모델 설정
│   ├── audio_capture.py  # WASAPI 루프백 캡처
│   ├── vad.py            # Silero VAD 래퍼
│   ├── asr.py            # whisper.cpp subprocess 래퍼
│   ├── translator.py     # NLLB (CTranslate2) 래퍼
│   └── overlay.py        # PyQt6 투명 오버레이
├── scripts/              # 모델·바이너리 다운로드 스크립트
├── bin/                  # whisper.cpp 바이너리 (Vulkan 빌드)
├── models/               # 모델 파일 (git 제외)
├── tests/                # 단위·통합 테스트
├── requirements.txt
└── README.md
```

---

## 설치

### 1. Python 3.11+ 가상환경

```bash
cd C:\Users\LSH\project\opus-translate
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. whisper.cpp Vulkan 바이너리 다운로드

```bash
python scripts\download_whisper.py
```

이 스크립트는 `bin/whisper-cli.exe`와 `models/ggml-large-v3-turbo-q5_0.bin`을 받습니다. Vulkan 드라이버가 없으면 CPU 바이너리로 대체됩니다.

### 3. NLLB 번역 모델 변환

```bash
python scripts\setup_nllb.py
```

HuggingFace에서 `facebook/nllb-200-distilled-1.3B`를 받아 CTranslate2 int8 형식으로 변환합니다. 약 1.5GB 디스크 공간 필요.

---

## 실행

```bash
python -m src.main
```

실행 후 영상을 재생하면 화면 하단에 한국어 자막이 오버레이됩니다.

### 핫키

| 조합 | 동작 |
|---|---|
| `Ctrl + Alt + T` | 자막 표시 / 숨김 토글 |
| `Ctrl + Alt + L` | 언어 모드 전환 (KO only / EN+KO) |
| `Ctrl + Alt + Q` | 애플리케이션 종료 |

---

## 성능 기대치

대상 하드웨어 기준 실측 예상 수치입니다.

| 지표 | 값 |
|---|---|
| 오디오 발화 → 한국어 자막 지연 | **2 ~ 3초** |
| CPU 평균 점유 | 30 ~ 40% |
| iGPU 평균 점유 | 50 ~ 70% |
| 메모리 사용 | 3 ~ 4 GB |
| 연속 시청 30분 중단 횟수 | 0 |

---

## 로드맵

- **v1 (현재)** — iGPU Vulkan Whisper + CPU NLLB, 듀얼 자막 오버레이
- **v2** — Ryzen AI NPU 전환(medium.en ONNX), iGPU/CPU 해방
- **v2.5** — EXAONE 3.5 또는 Qwen2.5 기반 LLM 번역 옵션 (관용구·밈 개선)
- **v3** — SRT 저장, 영상 파일 일괄 번역 모드, 일·중 입력 지원

---

## 라이선스 & 출처

- Whisper — MIT (OpenAI)
- whisper.cpp — MIT (ggerganov)
- NLLB-200 — CC-BY-NC-4.0 (Meta) · 개인·비상업 사용 한정
- Silero VAD — MIT
- CTranslate2 — MIT (OpenNMT)
- PyAudioWPatch — MIT

본 프로젝트 자체는 개인 사용 목적의 실험적 도구이며, NLLB 라이선스 조건에 따라 **상업적 재배포는 금지**됩니다.
