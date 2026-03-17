# CutAI — PRD v0.1

> 2026-03-17 | 민서 & 포로포
> Status: Draft
> License: MIT (오픈소스)

---

## 1. 한 줄 요약

> **자연어로 지시하면 AI가 편집해주는 로컬 영상 편집기.**

---

## 2. 문제

영상은 찍었다. 편집이 문제다.

- 촬영: 아이폰으로 10분이면 끝
- 편집: 몇 시간에서 며칠. 노동의 80%가 여기
- 기존 AI 도구: 클라우드 업로드 필수, 쇼츠 전용, 자연어 편집 불가, 비쌈

**민서도 브이로그 찍어놨는데 편집 못 하고 쌓아두는 중.**

---

## 3. 해결

```
$ cut edit ./vlog-raw/ \
  --instruction "재미없는 부분 잘라주고, 자막 넣고, 
                 밝은 BGM 깔아줘. 15분으로 줄여줘."
```

또는 대화형:
```
$ cut chat ./vlog-raw/

🎬 영상 분석 완료. 총 45분, 23개 장면 감지.

> 카페 가는 부분만 뽑아줘
✅ 카페 장면 3개 추출 (4분 32초)

> 자막 넣어줘
✅ 자막 생성 완료 (한국어)

> BGM 좀 깔아줘. 밝은 느낌으로.
✅ BGM 추가 (Upbeat Lo-fi, 15% 볼륨)

> 좋아, 렌더링해줘
🎬 렌더링 중... output/cafe-vlog.mp4 (1080p)
```

**완전 로컬. 클라우드 업로드 없음. 무료.**

---

## 4. 타깃 사용자

| 누구 | 왜 필요 | 어떻게 씀 |
|------|---------|----------|
| 브이로거/1인 크리에이터 | 촬영은 재밌는데 편집이 노동 | CLI/대화형으로 편집 지시 |
| 소규모 마케팅팀 | 편집자 고용 비용 절감 | 제품 영상, 소셜 콘텐츠 |
| 교육자 | 강의 영상 편집에 시간 낭비 | "빈 화면 잘라줘" 한마디 |
| 개발자 | 코드로 영상 편집 자동화 | Python/Node SDK로 배치 처리 |
| 기업 (NDA 영상) | 클라우드 업로드 불가 | 완전 로컬 처리 |

---

## 5. 킬러 피처: Edit Style Transfer

> 이미지 생성의 "스타일 전이"를 영상 편집에 적용한 **세계 최초** 구현.

### 컨셉

```
이미지: "지브리 스타일로 그려줘" → AI가 화풍 학습 → 적용
영상:  "딩고 스타일로 편집해줘" → AI가 편집 패턴 학습 → 적용
```

### Edit DNA — 편집 스타일의 구조화

편집 스타일을 정량적으로 분해한 스키마:

```yaml
edit_dna:
  rhythm:
    avg_cut_length: 3.2s         # 평균 컷 길이
    cut_variance: 1.8s           # 변동폭
    pacing_curve: "slow-fast-slow"
  transitions:
    jump_cut: 72%
    dissolve: 15%
    fade: 8%
    match_cut: 5%
  visual:
    color_temperature: "warm"
    saturation: 1.15
    contrast: 1.1
    zoom_frequency: 0.3/min
  audio:
    bgm_ratio: 0.15
    bgm_genre: "lo-fi"
    sfx_frequency: 2.1/min
    silence_tolerance: 0.8s
  subtitle:
    style: "large-center"
    has_emoji: true
    animation: "pop"
  structure:
    has_cold_open: true
    avg_segment_length: 45s
```

### 사용법

```bash
# 레퍼런스 영상에서 편집 DNA 추출
cut style extract "https://youtube.com/watch?v=xxx" --output style.yaml

# 내 영상에 적용
cut edit ./vlog.mp4 --style style.yaml

# 유튜버 채널 전체 스타일 학습
cut style learn --channel "@딩고뮤직" --samples 20 --output dingo.yaml

# 커뮤니티 스타일 프리셋
cut style install "vlog-korean-casual"
cut style install "cinematic-travel"
```

### 커뮤니티 생태계

이미지 생성의 LoRA 공유(Civitai)와 동일한 구조:
- 사용자가 편집 스타일을 추출해서 공유
- 별점/다운로드 수 기반 랭킹
- `awesome-edit-styles` 레포지토리

---

## 5-1. 핵심 차별점 (vs 경쟁)

| | Descript | Eddie AI | CapCut | OpusClip | **우리** |
|--|---------|---------|--------|----------|---------|
| 가격 | $24/월 | $100/월 | $21/월 | $19/월 | **$0 (MIT)** |
| 편집 방식 | 텍스트=영상 | 채팅+수동 | 수동 | 자동 클리핑 | **자연어 지시** |
| 로컬 실행 | ❌ | ❌ | ❌ | ❌ | **✅** |
| 프라이버시 | 클라우드 | 클라우드 | ByteDance 소유 | 클라우드 | **완전 로컬** |
| 영상 길이 | 제한 | 제한 | 15분 | 쇼츠 전용 | **무제한** |
| 결과물 | 러프컷 | 러프컷 | 기본 편집 | 쇼츠 | **완성본** |
| 감정 이해 | ❌ | ❌ | ❌ | ❌ | **✅** |
| 오픈소스 | ❌ | ❌ | ❌ | ❌ | **✅** |

---

## 6. 시스템 아키텍처

```
[입력: 원본 영상 + 자연어 지시]
            │
    ┌───────▼───────┐
    │   Analyzer     │  영상 이해
    │                │
    │  • 장면 감지    │  ← PySceneDetect
    │  • 음성 전사    │  ← Whisper (로컬)
    │  • 얼굴/인물    │  ← YOLO/MediaPipe
    │  • 품질 분석    │  ← 무음, 흔들림, 노출
    │  • 감정 분석    │  ← 오디오 톤 + 비주얼
    └───────┬───────┘
            │
    ┌───────▼───────┐
    │   Planner      │  편집 계획
    │                │
    │  자연어 지시    │  ← LLM (GPT/로컬 모델)
    │  → 편집 명령    │  → JSON Edit Plan
    │  변환           │
    └───────┬───────┘
            │
    ┌───────▼───────┐
    │   Editor       │  편집 실행
    │                │
    │  • 컷/트림      │  ← FFmpeg
    │  • 자막         │  ← Whisper → ASS
    │  • BGM          │  ← 자동 선택 + 믹싱
    │  • 색보정       │  ← FFmpeg 필터
    │  • 전환 효과    │  ← FFmpeg xfade
    │  • 속도 조절    │  ← FFmpeg setpts
    └───────┬───────┘
            │
    ┌───────▼───────┐
    │   Renderer     │  최종 렌더링
    │                │
    │  FFmpeg 파이프  │
    │  라인으로       │
    │  최종 MP4 출력  │
    └───────────────┘
```

---

## 7. 모듈별 상세

### 7.1 Analyzer (영상 분석기)

입력: 원본 영상 파일(들)
출력: VideoAnalysis JSON

```typescript
interface VideoAnalysis {
  duration: number;
  fps: number;
  resolution: { width: number; height: number };
  scenes: SceneInfo[];
  transcript: TranscriptSegment[];
  faces: FaceTrack[];
  quality: QualityReport;
}

interface SceneInfo {
  id: number;
  startTime: number;
  endTime: number;
  duration: number;
  description: string;        // LLM이 생성한 장면 설명
  emotion: string;            // neutral, happy, tense, boring...
  quality: number;            // 0-100 (흔들림, 노출, 포커스)
  hasSpeech: boolean;
  isSilent: boolean;
  transcript?: string;
  thumbnailPath: string;      // 대표 프레임
}

interface TranscriptSegment {
  startTime: number;
  endTime: number;
  text: string;
  speaker?: string;
  confidence: number;
}

interface QualityReport {
  silentSegments: TimeRange[];    // 무음 구간
  shakySegments: TimeRange[];     // 흔들리는 구간
  overexposed: TimeRange[];       // 과다 노출
  underexposed: TimeRange[];      // 부족 노출
  blurry: TimeRange[];            // 흐린 구간
}
```

서브모듈:
- **SceneDetector**: PySceneDetect (content-aware scene detection)
- **Transcriber**: Whisper (로컬, CPU/GPU)
- **FaceTracker**: MediaPipe 또는 YOLO
- **QualityAnalyzer**: FFmpeg signalstats + shakiness detect
- **SceneDescriber**: 비전 LLM으로 각 장면 설명 생성

### 7.2 Planner (편집 계획기)

입력: VideoAnalysis + 자연어 지시
출력: EditPlan JSON

```typescript
interface EditPlan {
  instruction: string;         // 원본 자연어 지시
  operations: EditOperation[];
  estimatedDuration: number;
  summary: string;             // 편집 요약 설명
}

type EditOperation =
  | CutOperation
  | SubtitleOperation
  | BGMOperation
  | ColorGradeOperation
  | TransitionOperation
  | SpeedOperation
  | CropOperation;

interface CutOperation {
  type: 'cut';
  action: 'keep' | 'remove';
  startTime: number;
  endTime: number;
  reason: string;              // "무음 구간" / "반복 내용" / "흔들림"
}

interface SubtitleOperation {
  type: 'subtitle';
  style: 'default' | 'emphasis' | 'karaoke';
  language: string;
  fontSize: number;
  position: 'bottom' | 'center' | 'top';
}

interface BGMOperation {
  type: 'bgm';
  mood: 'upbeat' | 'calm' | 'dramatic' | 'funny' | 'emotional';
  volume: number;              // 0-100 (나레이션 대비 %)
  fadein: number;              // 초
  fadeout: number;
}

interface ColorGradeOperation {
  type: 'colorgrade';
  preset: 'bright' | 'warm' | 'cool' | 'cinematic' | 'vintage';
  intensity: number;           // 0-100
}

interface TransitionOperation {
  type: 'transition';
  style: 'cut' | 'fade' | 'dissolve' | 'wipe';
  duration: number;
  between: [number, number];   // scene IDs
}

interface SpeedOperation {
  type: 'speed';
  factor: number;              // 0.5 = 슬로우, 2 = 2배속
  startTime: number;
  endTime: number;
}
```

핵심 LLM 프롬프트:
```
You are a professional video editor. Given a video analysis and a natural language 
editing instruction, generate an EditPlan.

Rules:
- "재미없는 부분 잘라줘" → Remove silent segments, shaky segments, and low-quality scenes
- "자막 넣어줘" → Add subtitles based on transcript
- "15분으로 줄여줘" → Keep highest-quality scenes, remove least important ones
- "카페 씬만 뽑아줘" → Match scene descriptions to "cafe/카페"
- "밝은 느낌으로" → Apply bright color grade + upbeat BGM

Output valid JSON matching the EditPlan schema.
```

### 7.3 Editor (편집 실행기)

입력: EditPlan + 원본 영상
출력: 편집된 MP4

FFmpeg 기반 편집 파이프라인:

```bash
# 1. 컷 편집 (keep/remove 구간 적용)
ffmpeg -i input.mp4 -vf "select='...',setpts=N/FRAME_RATE/TB" \
  -af "aselect='...',asetpts=N/SR/TB" cut.mp4

# 2. 색보정
ffmpeg -i cut.mp4 -vf "eq=brightness=0.05:contrast=1.1:saturation=1.2" color.mp4

# 3. 자막 입히기
ffmpeg -i color.mp4 -vf "ass=subtitles.ass" subtitled.mp4

# 4. BGM 믹싱
ffmpeg -i subtitled.mp4 -i bgm.mp3 \
  -filter_complex "[1:a]volume=0.15[bgm];[0:a][bgm]amix=inputs=2" \
  -c:v copy final.mp4
```

### 7.4 CLI & Chat Interface

```
cut <command> [options]

Commands:
  edit      원본 영상을 자연어 지시로 편집
  chat      대화형 편집 모드
  analyze   영상 분석만 (편집 없이)
  plan      편집 계획만 생성 (실행 없이)
  render    편집 계획 파일로 렌더링

Examples:
  cut edit ./raw.mp4 --instruction "재미없는 부분 잘라줘"
  cut edit ./vlog/ --instruction "15분으로 줄이고 자막 넣어줘" --output ./edited.mp4
  cut chat ./footage/
  cut analyze ./raw.mp4 --output analysis.json
```

---

## 8. 기술 스택

| 레이어 | 기술 | 이유 |
|--------|------|------|
| 언어 | **Python** | ML 생태계 + FFmpeg 바인딩 |
| 영상 처리 | **FFmpeg** | 업계 표준, 로컬, 무료 |
| 음성 전사 | **Whisper** (faster-whisper) | 로컬, 97%+ 정확도, 다국어 |
| 장면 감지 | **PySceneDetect** | 검증된 오픈소스 |
| 얼굴/인물 | **MediaPipe** / **YOLO** | 로컬, 빠름 |
| LLM (계획) | **OpenAI API** / **Ollama** (로컬) | 클라우드 or 완전 로컬 선택 |
| CLI | **Click** / **Typer** | Python CLI 표준 |
| 패키지 | **pip** + **PyPI** | `pip install cut-ai` |

### 로컬 전용 모드 (API 키 불필요)
- Whisper: 로컬
- 장면 감지: 로컬
- 품질 분석: 로컬
- LLM: **Ollama** (llama3, mistral 등)
- → **인터넷 없이도 완전 동작**

### 클라우드 모드 (더 나은 품질)
- LLM: OpenAI GPT-5.4 / Claude
- → 편집 계획 품질이 더 좋음

---

## 9. 프로젝트 구조

```
cut/
  __init__.py
  cli.py                    ← CLI 진입점 (Typer)
  chat.py                   ← 대화형 편집 모드
  
  analyzer/
    __init__.py
    scene_detector.py        ← PySceneDetect 래퍼
    transcriber.py           ← Whisper 래퍼
    face_tracker.py          ← MediaPipe/YOLO
    quality_analyzer.py      ← 흔들림/무음/노출 감지
    scene_describer.py       ← LLM 장면 설명
    
  planner/
    __init__.py
    edit_planner.py          ← 자연어 → EditPlan 변환
    prompts/
      edit_system.md         ← 시스템 프롬프트
      
  editor/
    __init__.py
    cutter.py                ← 컷/트림 편집
    subtitle.py              ← 자막 생성 (ASS)
    bgm.py                   ← BGM 선택 + 믹싱
    color.py                 ← 색보정
    transition.py            ← 전환 효과
    speed.py                 ← 속도 조절
    
  renderer/
    __init__.py
    ffmpeg_renderer.py       ← FFmpeg 파이프라인 실행
    
  models/
    types.py                 ← 모든 타입 정의
    
  assets/
    bgm/                     ← 기본 BGM (저작권 무료)
    fonts/                   ← 자막 폰트
    
  config.py                  ← 설정 관리
  
tests/
  test_analyzer.py
  test_planner.py
  test_editor.py
  
pyproject.toml
README.md
LICENSE                      ← MIT
```

---

## 10. MVP 범위 (Phase 1)

**최소한의 동작하는 제품:**

- [x] 영상 분석 (장면 감지 + 음성 전사 + 품질 분석)
- [x] 자연어 → 편집 계획 변환
- [x] 기본 편집 (컷/트림 + 자막 + BGM)
- [x] CLI (`cut edit` + `cut analyze`)
- [x] 로컬 전용 모드 (Ollama + Whisper)

**MVP로 가능한 것:**
```bash
cut edit ./vlog.mp4 --instruction "재미없는 부분 잘라줘, 자막 넣어줘"
```

---

## 11. 빌드 계획

### Phase 1: Core Engine (1-2주)
- [ ] 프로젝트 스캐폴드 (Python + pyproject.toml)
- [ ] Analyzer: 장면 감지 + Whisper 전사 + 품질 분석
- [ ] Planner: 자연어 → EditPlan (OpenAI + Ollama)
- [ ] Editor: 기본 컷/트림 (FFmpeg)
- [ ] Editor: 자막 생성 (Whisper → ASS)
- [ ] CLI: `cut edit` + `cut analyze`
- [ ] 민서 브이로그로 독도그푸딩 테스트

### Phase 2: Edit Style Transfer (2-3주)
- [ ] Edit DNA 스키마 정의 (YAML)
- [ ] 스타일 추출기 (`cut style extract`) — 영상에서 Edit DNA 자동 추출
- [ ] 스타일 적용기 — Edit DNA → FFmpeg 파라미터 변환
- [ ] 채널 스타일 학습 (`cut style learn`) — 여러 영상에서 평균 스타일
- [ ] 대화형 모드 (`cut chat`)
- [ ] 편집 미리보기 (저해상도 프리뷰)

### Phase 3: Intelligence (2-3주)
- [ ] Engagement Score — 멀티모달 LLM + 오디오 에너지 기반 장면 흥미도 산출
- [ ] 개인 학습 — 사용자 피드백 기억 (로컬 JSON few-shot)
- [ ] 멀티 영상 편집 (여러 클립 → 하나의 영상)
- [ ] 스마트 하이라이트 (가장 재미있는 순간 자동 추출)
- [ ] 커뮤니티 스타일 마켓플레이스 (awesome-edit-styles)

### Phase 4: GitHub Launch (1주)
- [ ] README.md (영어, GIF 데모 포함)
- [ ] 설치 가이드 (pip install)
- [ ] 예제 비디오 + 결과물
- [ ] GitHub Actions CI
- [ ] PyPI 배포
- [ ] Hacker News / Reddit 론칭

---

## 12. 이름 후보

| 이름 | 의미 | 도메인/PyPI |
|------|------|-----------|
| **cut** | 영상 편집의 기본 동작 | 짧고 강렬 |
| **autocut** | 자동 편집 | 이미 있음 (1.4K stars) |
| **editai** | AI 편집 | 직관적 |
| **reelforge** | 릴을 만든다 | 유니크 |
| **montage** | 몽타주 편집 | 클래식 |
| **rushcut** | 러시(원본) → 컷 | 편집 용어 |

> 이름은 나중에 같이 정하자.

---

## 13. 성공 지표

### 3개월
- GitHub ⭐ 5,000+
- PyPI 주간 다운로드 1,000+
- 민서 브이로그 실제 편집에 사용

### 6개월
- GitHub ⭐ 20,000+
- Hacker News 프론트페이지
- 커뮤니티 기여자 10명+

### 12개월
- GitHub ⭐ 50,000+
- 호스티드 버전 론칭 (수익화 선택지)

---

## 14. 경쟁사 한계 정리

| 경쟁사 | 핵심 한계 |
|--------|----------|
| Descript ($24/월) | 텍스트=영상이지만 자연어 지시 불가, 자주 크래시, AI 크레딧 하루 만에 소진, 내보내기 품질 나쁨 |
| Eddie AI ($100-333/월) | 결과물 퀄리티 낮음, 프로젝트 제한 (A-roll 10개), 멀티캠 미지원, 원클릭 아님 |
| CapCut ($21/월) | 15분 제한, 단일 트랙, ByteDance 콘텐츠 소유권 탈취, 미국 밴 |
| OpusClip ($19/월) | 쇼츠 전용 (롱폼 불가), 자연어 편집 불가 |
| VEED ($12-24/월) | 자연어 편집 없음, 기본 도구만 |
| 오픈소스 전체 | 자연어 편집 없음, 대부분 미완성 or 하이라이트 추출만 |

---

## 15. 리스크 & 대응

| 리스크 | 확률 | 대응 |
|--------|------|------|
| Whisper 정확도 부족 (한국어) | 중 | faster-whisper 한국어 모델 + 후처리 |
| LLM 편집 계획 품질 낮음 | 높음 | 프롬프트 엔지니어링 + 피드백 루프 |
| FFmpeg 복잡성 | 중 | 각 편집 유형별 검증된 명령어 라이브러리 |
| 로컬 LLM 성능 부족 | 중 | Ollama + 작은 모델로도 동작하게 설계 |
| 유사 프로젝트 등장 | 높음 | 선점 + 커뮤니티 빌딩 |
| 저작권 BGM 문제 | 낮음 | CC0 BGM만 기본 포함 |

---

_"촬영은 사람이, 편집은 AI가."_
