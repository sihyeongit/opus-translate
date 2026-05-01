# Opus Translate

PC 내부 오디오를 실시간으로 캡처해 **영어 → 한국어**로 번역·자막 표시하는 오프라인 데스크탑 도구.

유튜브, 넷플릭스, 온라인 강의, 팟캐스트 등 모든 시스템 사운드에 적용됩니다. 유료 서비스 없이 로컬에서 동작하며, 비용은 0원입니다.

---

## 주요 특징

- **완전 오프라인 / 무료** — 외부 API 호출 없음, 오픈소스 모델·런타임만 사용
- **고품질 번역** — faster-whisper `medium.en` + Meta NLLB-200 조합
- **상주형 ASR** — Whisper 모델을 프로세스 안에 유지해 발화마다 모델을 다시 로드하지 않음
- **짧은 음성 병합** — 짧은 VAD 조각을 잠깐 모아 Whisper 호출 횟수와 문장 절단을 줄임
- **자막 품질 보정** — 짧은 발화 병합, 고유명사 보존, 반복 번역 후처리
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
| iGPU | AMD Radeon 890M (RDNA 3.5) |
| RAM | 24GB LPDDR5X 7500 MT/s |
| OS | Windows 11 |

현재 코드 경로는 CPU int8 추론 기준입니다. 다른 AMD/Intel 노트북에서도 동작 가능하지만, CPU 코어 수와 메모리 대역폭에 따라 실시간성이 달라질 수 있습니다.

---

## 아키텍처 개요

```
 ┌─────────────────────┐     ┌──────────────┐     ┌──────────────────────┐
 │ WASAPI Loopback     │────▶│ Silero VAD   │────▶│ faster-whisper       │
 │ (PyAudioWPatch)     │     │ (발화 감지)   │     │ medium.en · CPU int8 │
 └─────────────────────┘     └──────────────┘     └──────────────────────┘
                                                               │
                                                               ▼
 ┌──────────────────────┐    ┌──────────────────────────────────────────┐
 │ PyQt6 투명 오버레이   │◀───│ NLLB-200-distilled-1.3B · CTranslate2   │
 │ (EN + KO 자막)       │    │ (int8 · CPU 추론)                        │
 └──────────────────────┘    └──────────────────────────────────────────┘
```

**자원 배분**:
- CPU: 오디오 I/O, VAD, ASR, 번역 (NLLB)
- iGPU/NPU: 현재 코드 경로에서는 미사용

현재 구현 기준의 상세 맥락은 `PROJECT_CONTEXT.md`를 참고하세요.

---

## 폴더 구조

```
opus-translate/
├── src/                  # 애플리케이션 소스
│   ├── main.py           # 엔트리포인트 · 파이프라인 조립
│   ├── config.py         # 경로, 핫키, 모델 설정
│   ├── audio_capture.py  # WASAPI 루프백 캡처
│   ├── vad.py            # Silero VAD 래퍼
│   ├── segment_merge.py  # ASR 전 짧은 음성 조각 병합
│   ├── asr.py            # faster-whisper ASR 래퍼
│   ├── translator.py     # NLLB (CTranslate2) 래퍼
│   ├── quality.py        # 번역 전/후처리 품질 보정
│   └── overlay.py        # PyQt6 투명 오버레이
├── scripts/              # 모델 준비 스크립트
├── bin/                  # legacy whisper.cpp 바이너리 (현재 런타임 미사용)
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

### 2. 런타임 모델 준비

```bash
python scripts\setup_all.py
```

이 스크립트는 faster-whisper ASR 모델(`medium.en`)을 Hugging Face cache에 미리 받고, `facebook/nllb-200-distilled-1.3B`를 CTranslate2 int8 형식으로 변환해 `models\nllb-200-distilled-1.3B-ct2-int8\`에 저장합니다.

### 3. 환경 점검

```bash
python -m src.doctor
```

Python 버전, 주요 패키지, ASR 모델 cache, NLLB 모델 파일, WASAPI loopback 장치를 확인합니다.

---

## 실행

```bash
python -m src.main
```

실행 후 영상을 재생하면 화면 하단에 한국어 자막이 오버레이됩니다.

Windows에서 매번 가상환경을 활성화하기 번거로우면 `run_opus_translate.bat`을 더블클릭해 실행할 수 있습니다. 환경 점검은 `doctor.bat`을 사용하세요.

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
| CPU 평균 점유 | 30 ~ 60% |
| iGPU 평균 점유 | 현재 코드 경로에서는 사용하지 않음 |
| 메모리 사용 | 3 ~ 4 GB |
| 연속 시청 30분 중단 횟수 | 0 |

---

## 로드맵

- **v1 (현재)** — faster-whisper CPU int8 + CPU NLLB, 듀얼 자막 오버레이
- **v2** — Ryzen AI NPU 전환(medium.en ONNX), iGPU/CPU 해방
- **v2.5** — EXAONE 3.5 또는 Qwen2.5 기반 LLM 번역 옵션 (관용구·밈 개선)
- **v3** — SRT 저장, 영상 파일 일괄 번역 모드, 일·중 입력 지원

---

## 라이선스 & 출처

- Whisper — MIT (OpenAI)
- faster-whisper — MIT (SYSTRAN)
- whisper.cpp — MIT (ggerganov)
- NLLB-200 — CC-BY-NC-4.0 (Meta) · 개인·비상업 사용 한정
- Silero VAD — MIT
- CTranslate2 — MIT (OpenNMT)
- PyAudioWPatch — MIT

본 프로젝트 자체는 개인 사용 목적의 실험적 도구이며, NLLB 라이선스 조건에 따라 **상업적 재배포는 금지**됩니다.
