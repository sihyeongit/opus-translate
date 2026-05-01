# Opus Translate · 빠른 시작

## 1. Python 환경

Python **3.10 ~ 3.13** 권장. 3.13.7에서 테스트 확인됨.

가상환경 생성 (선택, 권장):

```bash
cd C:\Users\LSH\project\opus-translate
python -m venv .venv
.venv\Scripts\activate
```

## 2. 의존성 설치

```bash
pip install -r requirements.txt
```

주요 패키지:
- `PyAudioWPatch` — WASAPI loopback 캡처
- `silero-vad` — 음성 구간 감지
- `faster-whisper` — Whisper ASR
- `ctranslate2` + `transformers` — NLLB 번역
- `PyQt6` — 투명 오버레이 UI
- `keyboard`, `pywin32` — 글로벌 핫키 & Win32 연동

## 3. 모델 준비 (1회)

```bash
python scripts\setup_all.py
```

이 스크립트가 수행하는 작업:
1. **faster-whisper medium.en** 모델 다운로드 → Hugging Face cache
2. **NLLB-200-distilled-1.3B** HuggingFace → CTranslate2 int8 변환 → `models\nllb-...\` (~1.5GB)

총 약 **1.5GB+ 디스크 공간** 필요. ASR 모델 cache까지 포함하면 추가 공간이 필요합니다. 네트워크 상태에 따라 10~30분 소요될 수 있습니다.

## 4. 환경 점검

```bash
python -m src.doctor
```

`src.doctor`는 Python 버전, 주요 패키지, ASR 모델 cache, NLLB 모델 파일, WASAPI loopback 장치를 확인합니다. 실패 항목이 있으면 먼저 해결한 뒤 실행하세요.

## 5. 실행

```bash
python -m src.main
```

시작하면 화면 하단에 "오퍼스 트랜슬레이트 준비 완료." 자막이 잠시 뜹니다. 이후 PC에서 영어 오디오(유튜브/넷플릭스/Zoom 등)를 재생하면 한국어 자막이 2~3초 지연 후 표시됩니다.

매번 가상환경을 활성화하기 번거로우면 프로젝트 루트의 `run_opus_translate.bat`을 더블클릭하세요. 환경 점검은 `doctor.bat`을 더블클릭하면 됩니다.

### 핫키

| 조합 | 동작 |
|---|---|
| `Ctrl+Alt+T` | 자막 표시/숨김 |
| `Ctrl+Alt+L` | 언어 모드 (KO only ↔ EN+KO) |
| `Ctrl+Alt+Q` | 종료 |

## 6. 문제 해결

### "No loopback endpoint found"
Windows 기본 재생 장치가 바뀌었을 가능성. 사운드 설정에서 기본 장치를 명시한 뒤 재실행.

### 자막이 뜨지 않음
```bash
python -m src.audio_capture
```
10초간 오디오 캡처 테스트. RMS 값이 0에 가까우면 장치 문제, 값이 뜨면 캡처는 정상 → VAD/모델 쪽을 의심.

### 첫 실행이 오래 걸림
`python scripts\setup_all.py`를 먼저 실행하지 않았다면 `faster-whisper`가 `medium.en` 모델을 Hugging Face cache에 받는 중일 수 있습니다. 네트워크가 막혀 있으면 모델 다운로드 단계에서 실패합니다.

### 전체화면 영상 위에 자막이 안 뜸
넷플릭스/유튜브 전체화면(F11 / F)은 exclusive mode라 오버레이가 가려질 수 있음. **창 모드(기본)** 또는 브라우저 전체화면(F11)을 사용하면 뜸. 게임의 fullscreen exclusive는 창 모드로 전환 필요.

### CPU/GPU 과부하로 끊김
`src\config.py`에서:
- `AsrConfig.model_size` 를 `small.en`으로 변경
- `TranslatorConfig.intra_threads` 를 4로 감소
- `AsrConfig.beam_size` 를 1로 감소

## 7. 구성 요소 단독 테스트

```bash
# 환경 점검
python -m src.doctor

# 루프백 캡처 10초 측정
python -m src.audio_capture

# 스모크 테스트
python -m pytest tests/
```
