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
- `ctranslate2` + `transformers` — NLLB 번역
- `PyQt6` — 투명 오버레이 UI
- `keyboard`, `pywin32` — 글로벌 핫키 & Win32 연동

## 3. 모델 & 바이너리 다운로드 (1회)

```bash
python scripts\setup_all.py
```

이 스크립트가 수행하는 작업:
1. **whisper.cpp 바이너리** 다운로드 → `bin\whisper-cli.exe` (+ DLL들)
2. **ggml-large-v3-turbo-q5_0.bin** 모델 다운로드 → `models\` (~574MB)
3. **NLLB-200-distilled-1.3B** HuggingFace → CTranslate2 int8 변환 → `models\nllb-...\` (~1.5GB)

총 약 **2GB 디스크 공간** 필요. 네트워크 상태에 따라 10~30분 소요.

### 수동 다운로드가 필요한 경우

whisper.cpp 릴리스 URL이 바뀌었다면:
1. <https://github.com/ggml-org/whisper.cpp/releases/latest> 에서 `whisper-bin-x64.zip` (또는 Vulkan 빌드) 다운로드
2. 압축 해제 후 `whisper-cli.exe`와 모든 `.dll`을 `bin\`에 복사

Vulkan 가속판이 없다면 CPU 바이너리도 동작함. 그 경우 `src\config.py`에서 `use_vulkan=False`로 설정.

## 4. 실행

```bash
python -m src.main
```

시작하면 화면 하단에 "오퍼스 트랜슬레이트 준비 완료." 자막이 잠시 뜹니다. 이후 PC에서 영어 오디오(유튜브/넷플릭스/Zoom 등)를 재생하면 한국어 자막이 2~3초 지연 후 표시됩니다.

### 핫키

| 조합 | 동작 |
|---|---|
| `Ctrl+Alt+T` | 자막 표시/숨김 |
| `Ctrl+Alt+L` | 언어 모드 (KO only ↔ EN+KO) |
| `Ctrl+Alt+Q` | 종료 |

## 5. 문제 해결

### "No loopback endpoint found"
Windows 기본 재생 장치가 바뀌었을 가능성. 사운드 설정에서 기본 장치를 명시한 뒤 재실행.

### 자막이 뜨지 않음
```bash
python -m src.audio_capture
```
10초간 오디오 캡처 테스트. RMS 값이 0에 가까우면 장치 문제, 값이 뜨면 캡처는 정상 → VAD/모델 쪽을 의심.

### Vulkan 초기화 실패
`whisper-cli.exe` 실행 시 Vulkan 에러가 나면 CPU 빌드 바이너리로 교체. 성능은 떨어지지만(약 RTF 0.5~1) 품질은 동일.

### 전체화면 영상 위에 자막이 안 뜸
넷플릭스/유튜브 전체화면(F11 / F)은 exclusive mode라 오버레이가 가려질 수 있음. **창 모드(기본)** 또는 브라우저 전체화면(F11)을 사용하면 뜸. 게임의 fullscreen exclusive는 창 모드로 전환 필요.

### CPU/GPU 과부하로 끊김
`src\config.py`에서:
- `AsrConfig.model` 을 `ggml-medium.en-q5_0.bin`으로 변경
- `TranslatorConfig.intra_threads` 를 4로 감소
- `AsrConfig.beam_size` 를 1로 감소

## 6. 구성 요소 단독 테스트

```bash
# 루프백 캡처 10초 측정
python -m src.audio_capture

# 스모크 테스트
python -m pytest tests/
```
