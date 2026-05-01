# Opus Translate 프로젝트 맥락

이 문서는 이후 작업에서 프로젝트 맥락을 빠르게 복원하기 위한 기준 문서다. README/QUICKSTART의 의도와 현재 소스 구현이 일부 다르므로, 실제 코드를 우선 기준으로 정리한다.

## 프로젝트 목적

Opus Translate는 Windows PC의 시스템 오디오를 WASAPI loopback으로 캡처한 뒤, 영어 음성을 한국어 자막으로 실시간 표시하는 로컬 데스크탑 도구다.

핵심 목표는 다음과 같다.

- 외부 번역/음성 API 없이 로컬에서 동작한다.
- 유튜브, 넷플릭스, 강의, 팟캐스트 등 기본 재생 장치로 나가는 오디오를 대상으로 한다.
- 영어 원문과 한국어 번역을 PyQt6 투명 오버레이로 표시한다.
- 실시간성을 위해 오디오 캡처, VAD, ASR, 번역, UI를 분리된 단계로 운영한다.

## 현재 코드 기준 파이프라인

현재 엔트리포인트는 `python -m src.main`이다.

```text
Windows system audio
  -> src.audio_capture.LoopbackCapture
  -> src.vad.SileroVAD
  -> src.asr.FasterWhisperASR
  -> src.translator.NLLBTranslator
  -> src.overlay.SubtitleOverlay
```

각 단계의 역할은 다음과 같다.

- `src/audio_capture.py`: PyAudioWPatch로 기본 출력 장치의 WASAPI loopback endpoint를 찾고, 오디오를 16 kHz mono float32 frame으로 변환한다.
- `src/vad.py`: Silero VAD로 32 ms frame을 speech segment로 묶는다. preroll/postroll을 붙여 단어 앞뒤가 잘리지 않게 한다.
- `src/asr.py`: `faster-whisper`를 인프로세스로 로드해 영어 음성을 문장 단위 텍스트로 변환한다.
- `src/translator.py`: CTranslate2로 변환된 NLLB-200 distilled 1.3B int8 모델을 사용해 영어를 한국어로 번역한다.
- `src/overlay.py`: PyQt6 frameless, always-on-top, click-through overlay에 최근 자막을 표시한다.
- `src/main.py`: 전체 파이프라인을 조립하고 worker thread, bounded queue, hotkey를 관리한다.

## 중요한 구현 상태

현재 공식 ASR 경로는 `src/asr.py`의 `faster-whisper` CPU int8 백엔드다. 즉 현재 런타임에서는 `bin/whisper-cli.exe`와 `models/ggml-large-v3-turbo-q5_0.bin`이 ASR 경로에 직접 쓰이지 않는다.

현재 ASR 설정은 `src/config.py` 기준이다.

- model: `medium.en`
- device: `cpu`
- compute_type: `int8`
- cpu_threads: `12`
- num_workers: `2`
- beam_size: `1`
- language: `en`
- initial_prompt: 빈 문자열

현재 번역 설정은 다음과 같다.

- model_dir: `models/nllb-200-distilled-1.3B-ct2-int8`
- tokenizer: `facebook/nllb-200-distilled-1.3B`
- source language: `eng_Latn`
- target language: `kor_Hang`
- device: `cpu`
- compute_type: `int8`
- intra_threads: `8`
- beam_size: `2`

## 실행과 의존성

기본 실행 명령:

```powershell
python -m src.main
```

편의 실행 파일:

```powershell
.\run_opus_translate.bat
```

테스트 명령:

```powershell
python -m pytest tests/
```

환경 점검 명령:

```powershell
python -m src.doctor
```

`src.doctor`는 Python 버전, 주요 패키지 import 가능 여부, faster-whisper 모델 cache, NLLB 모델 파일, WASAPI loopback endpoint를 확인한다.

오디오 캡처 단독 확인:

```powershell
python -m src.audio_capture
```

주의할 점:

- `tests/test_smoke.py`는 Silero VAD 중심의 최소 smoke test만 포함한다. ASR, 번역, UI, 실제 오디오 loopback은 테스트 범위에 없다.
- `scripts/setup_asr.py`는 `AsrConfig.model_size` 기준으로 faster-whisper 모델을 Hugging Face cache에 미리 받는다.
- `scripts/download_whisper.py`는 legacy whisper.cpp 자산을 받는 선택 스크립트이며, 현재 `scripts/setup_all.py` 경로에는 포함되지 않는다.

## 런타임 구조와 동시성

`src.main.Pipeline`은 다음 queue와 thread를 사용한다.

- `_asr_q`: VAD가 만든 `SpeechSegment`를 ASR worker로 전달한다. maxsize는 16이다.
- `_mt_q`: ASR 결과인 `TranscribedSegment`를 번역 worker로 전달한다. maxsize는 16이다.
- worker thread: `vad`, `asr`, `mt` 세 개가 daemon thread로 동작한다.

back-pressure 정책은 queue가 가득 차면 오래된 입력을 기다리지 않고 segment/transcription을 drop하며 log warning을 남기는 방식이다. 실시간 자막 도구이므로 모든 발화를 보존하기보다 지연 누적을 피하는 쪽에 가깝다.

ASR loop에는 문장 fragment buffering이 있다. VAD가 5초 단위로 긴 발화를 잘라 headless fragment가 생기는 문제를 줄이기 위해, 마지막 문장이 `.?!`로 끝나지 않으면 다음 chunk와 합친다. 단, pending text가 너무 오래 남으면 강제로 flush한다.

노이즈 필터는 `_is_noise()`에 있으며 다음을 제거한다.

- `[music]`, `[silence]`, punctuation-only output
- Whisper가 저에너지 오디오에서 자주 환각하는 YouTube ending phrase

## UI와 핫키

오버레이는 `src.overlay.SubtitleOverlay`가 담당한다.

- 기본 표시 모드는 영어+한국어(`EN_KO`)다.
- `Ctrl+Alt+T`: 표시/숨김
- `Ctrl+Alt+L`: 한국어만 보기와 영어+한국어 보기 전환
- `Ctrl+Alt+Q`: 종료

오버레이는 click-through이므로 기본적으로 아래 앱의 입력을 방해하지 않는다. exclusive fullscreen 앱에서는 overlay가 가려질 수 있으므로 창 모드나 borderless/windowed fullscreen이 더 안전하다.

## 모델과 대용량 파일

`.gitignore`는 `models/`, `bin/`, `logs/`, capture/debug 산출물을 제외한다. 현재 workspace에는 다음 대용량 런타임 산출물이 존재한다.

- `bin/`: whisper.cpp 관련 exe/dll 파일들
- `models/ggml-large-v3-turbo-q5_0.bin`: whisper.cpp용 GGML 모델
- `models/nllb-200-distilled-1.3B-ct2-int8/`: 현재 번역 런타임이 사용하는 CT2 int8 모델

현재 `faster-whisper`의 `medium.en` 모델은 Hugging Face cache에 자동 다운로드될 수 있으며, repo의 `models/` 경로와 별개일 수 있다.

## 현재 리스크와 정리 필요 항목

우선순위가 높은 항목:

- `config.py`의 `LOGS_DIR`는 정의되어 있지만 현재 logging file sink는 없다.
- `AudioConfig.capture_channels`는 현재 `LoopbackCapture` 생성에 사용되지 않는다.
- `VadConfig.min_silence_ms` 옆에 한국어 인라인 주석 `#원래 500`이 남아 있어 설정 변경 의도는 보이지만 기준값 결정 근거는 문서화되어 있지 않다.

후속 개선 후보:

- 실제 오디오 없이 ASR/번역 wrapper를 mock하는 pipeline 단위 테스트를 추가한다.
- overlay resize/screen 변경 대응을 추가한다.
- log 파일 저장과 성능 지표 출력 형식을 정리한다.

## 작업 시 기준

새 작업을 시작할 때는 다음 순서로 확인한다.

1. `src/config.py`에서 현재 성능/모델 설정을 확인한다.
2. ASR 관련 작업이면 `src/asr.py`가 faster-whisper 기반이라는 점을 우선 반영한다.
3. 모델 설치 관련 작업이면 README보다 `scripts/`와 실제 런타임 사용 경로의 차이를 먼저 확인한다.
4. 실시간성 관련 변경은 queue backlog, ASR 처리 시간(`asr_ms`), segment 길이(`seg_ms`), MT 시간(`mt_ms`) log를 기준으로 판단한다.
5. 자막 품질 변경은 ASR fragment merge, `_is_noise()`, NLLB stateless 번역 제약을 함께 고려한다.
