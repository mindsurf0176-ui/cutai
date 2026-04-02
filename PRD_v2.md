# CutAI — PRD v2

> 2026-04-03 | 민서 & 포로포
> Status: Active
> Previous: PRD.md (v0.1)
> License: MIT

---

## 0. v1 → v2: 뭐가 달라졌나

v1 PRD는 "만들자" 단계였다. 지금은 **만들었다**. v0.1.0-alpha 출시 완료, 197개 테스트 통과, 데스크톱 앱도 있다.

v2는 "어떻게 이기느냐" 단계다.

**v1에서 완료된 것:**
- ✅ Core pipeline (analyze → plan → edit → render)
- ✅ Edit Style Transfer (DNA 추출 → 적용 → 학습)
- ✅ EDITSTYLE.md (Google Stitch DESIGN.md의 영상 편집 버전)
- ✅ Smart Highlights (engagement scoring → reel 생성)
- ✅ Desktop app (Tauri, macOS alpha)
- ✅ CLI 완성 (16개 커맨드)
- ✅ 로컬 전용 모드 (API 키 없이 동작)

**v2에서 해결할 문제:**
1. "편집"이 아니라 "편집 워크플로우"를 해결해야 한다
2. 경쟁자들이 agentic editing으로 진화 중 — 우리도 가야 한다
3. 오픈소스 + 로컬의 강점을 극대화하는 방향
4. 커뮤니티 생태계가 아직 0이다

---

## 1. 한 줄 요약

> **자연어로 지시하면 AI 에이전트가 알아서 편집해주는, 오픈소스 로컬 영상 편집 플랫폼.**

v1: "자연어로 지시하면 AI가 편집해주는 로컬 영상 편집기"
v2: **편집기 → 편집 플랫폼**. 에이전트, 생태계, 확장성.

---

## 2. 2026년 시장 현실

### 확인된 트렌드 (1차 소스 교차검증)

| 트렌드 | 영향 | CutAI 대응 |
|--------|------|-----------|
| **Agentic editing** — 단일 기능 → 멀티스텝 자율 편집 | 에디터가 "크리에이티브 디렉터" 역할로 전환 | Phase 1: Agent Mode |
| **로컬 퍼스트** — 클라우드 업로드 거부 확산 (NDA, 의료, 기업) | 이미 우리 강점. Apple Silicon 최적화 필요 | Phase 2: Metal 가속 |
| **NLE 연동 필수** — AI가 MP4만 뱉으면 편집자가 안 씀 | Premiere/DaVinci 프로젝트 파일 내보내기 | Phase 3: NLE Export |
| **EDITSTYLE.md 파급** — Google Stitch DESIGN.md가 UI 판을 바꿈 | 영상 편집판 표준 될 가능성 | ✅ 이미 구현. 선점 |
| **커뮤니티 프리셋 경제** — LoRA/Civitai처럼 스타일 공유 문화 | 생태계 = 해자 | Phase 2: Style Hub |

### 경쟁 구도 (2026-04 기준)

| | 가격 | 편집 방식 | 로컬 | 오픈소스 | Agentic | NLE 연동 |
|--|------|----------|------|---------|---------|---------|
| Descript | $24/월 | 텍스트=영상 | ❌ | ❌ | ❌ | 제한적 |
| Wideframe | $$$$ | 에이전트 | ✅ (M칩) | ❌ | ✅ | Premiere |
| CapCut | $21/월 | 수동+AI | ❌ | ❌ | ❌ | ❌ |
| OpusClip | $19/월 | 자동 클리핑 | ❌ | ❌ | ❌ | ❌ |
| Cutback | $?/월 | 러프컷 자동화 | 하이브리드 | ❌ | 부분적 | Premiere |
| **CutAI** | **$0** | **자연어+에이전트** | **✅** | **✅** | **Phase 1** | **Phase 3** |

**우리의 포지션: Wideframe의 에이전트 편집 철학 + 완전 오픈소스 + $0.**

---

## 3. 핵심 개선 영역

### 3.1 🤖 Agent Mode (최우선)

현재 CutAI는 **단일 파이프라인**: analyze → plan → render. 사용자가 매 단계를 명시적으로 지시해야 한다.

**Agent Mode**: 사용자가 "15분짜리 카페 브이로그 만들어줘"라고 하면, 에이전트가 알아서:
1. 원본 영상들 분석
2. 카페 관련 장면 식별
3. 편집 계획 수립
4. 렌더링
5. "이렇게 했는데 어때?" 하고 보여줌
6. 피드백 반영해서 재편집

```bash
# 현재 (v1)
cutai analyze vlog.mp4
cutai plan vlog.mp4 -i "카페 씬만 뽑아줘"
cutai edit vlog.mp4 -i "카페 씬만 뽑아줘, 자막 넣어줘"

# Agent Mode (v2)
cutai agent ./footage/ \
  --goal "15분짜리 카페 브이로그. 따뜻하고 캐주얼한 느낌." \
  --iterations 3
```

**구현 설계:**

```
cutai agent <input> --goal "<목표>"
       │
       ▼
┌──────────────────┐
│  Agent Loop       │
│                   │
│  1. Analyze all   │ ← 멀티 영상 일괄 분석
│  2. Scene select  │ ← 목표 기반 장면 선택 (LLM)
│  3. Style decide  │ ← EDITSTYLE.md or 목표에서 추론
│  4. Plan + Render │ ← 기존 파이프라인 재사용
│  5. Self-evaluate │ ← 결과물 분석 + 목표 대비 평가
│  6. Iterate       │ ← 피드백 루프 (자동 or 사용자)
└──────────────────┘
```

**핵심 차별화**: 다른 에이전트 편집 도구들은 클라우드 + 유료. 우리는 **로컬에서 돌아가는 오픈소스 에이전트**.

---

### 3.2 🔌 MCP Server (Tool 생태계 연결)

Google Stitch가 MCP Server로 Claude Code/Cursor와 연결된 것처럼, CutAI도 MCP Server를 제공.

```json
// Claude Code, Cursor 등에서:
{
  "mcpServers": {
    "cutai": {
      "command": "cutai",
      "args": ["mcp-server"]
    }
  }
}
```

**노출할 Tool들:**
| Tool | 설명 |
|------|------|
| `cutai_analyze` | 영상 분석 |
| `cutai_plan` | 편집 계획 생성 |
| `cutai_edit` | 편집 + 렌더링 |
| `cutai_style_extract` | 스타일 추출 |
| `cutai_style_apply` | 스타일 적용 |
| `cutai_highlights` | 하이라이트 생성 |
| `cutai_engagement` | 장면별 참여도 분석 |
| `cutai_editstyle_parse` | EDITSTYLE.md 파싱 |

**왜 중요한가**: 개발자가 자신의 AI 워크플로우(Claude Code로 코딩하면서 "이 영상도 편집해줘")에 CutAI를 자연스럽게 통합. 생태계 진입.

---

### 3.3 📐 EDITSTYLE.md 생태계 확장

이미 구현했지만, 생태계를 만들어야 의미가 있다.

**Phase 1 (✅ 완료):** 파서 + 컨버터 + CLI
**Phase 2:** 
- `cutai style extract --format md` — 영상에서 바로 EDITSTYLE.md 생성
- 유튜버 채널 스타일 추출 자동화
- `awesome-editstyles` GitHub 레포 런칭
- README에 EDITSTYLE.md 뱃지 + 표준화 문서

**Phase 3:**
- EDITSTYLE.md 온라인 에디터 (웹)
- 커뮤니티 업로드/다운로드 허브
- 별점/다운로드 랭킹

---

### 3.4 ⚡ 성능 — Apple Silicon 최적화

현재 병목: Whisper 전사 + FFmpeg 렌더링.

| 최적화 | 효과 | 난이도 |
|--------|------|--------|
| **MLX Whisper** | Apple Silicon 네이티브 전사, 3-5x 빠름 | 중 |
| **Metal 가속 FFmpeg** | VideoToolbox 인코딩 (H.264/HEVC) | 하 |
| **병렬 장면 분석** | 장면별 독립 분석을 멀티코어 활용 | 중 |
| **증분 분석 캐시** | 같은 영상 재분석 시 캐시 히트 | 하 |
| **스트리밍 렌더** | 전체 계획 완성 전에 부분 렌더 시작 | 상 |

목표: **10분 영상 → 1분 이내 전체 파이프라인** (M3 Pro 기준)

---

### 3.5 🎬 NLE 프로젝트 파일 Export

현재는 MP4만 내보낸다. 프로 편집자는 이걸 안 쓴다.

**지원 포맷:**
| 포맷 | NLE | 우선순위 |
|------|-----|---------|
| **FCPXML** | Final Cut Pro | 1순위 (macOS 유저 베이스) |
| **EDL** | DaVinci / 범용 | 2순위 (가장 호환성 높음) |
| **.prproj** (XML) | Premiere Pro | 3순위 (시장 점유율 1위) |

```bash
cutai edit vlog.mp4 -i "편집해줘" --export fcpxml
# → output/vlog_edited.fcpxml (Final Cut Pro에서 바로 열기)
```

**핵심**: AI가 만든 편집을 **시작점**으로 쓸 수 있게. "AI가 러프컷 → 사람이 파인튜닝" 워크플로우.

---

### 3.6 🌐 Web UI

데스크톱 앱은 있지만 설치 허들이 높다. 브라우저에서 바로 쓸 수 있는 Web UI.

**기술:**
- 프론트: React (기존 데스크톱 UI 재사용)
- 백엔드: `cutai server` (이미 있음)
- 파일 처리: 로컬 서버, 브라우저에서 업로드만

**핵심 화면:**
1. **Upload** — 드래그앤드롭
2. **Timeline** — 장면별 썸네일 + engagement 바
3. **Chat** — 자연어 편집 지시
4. **Style** — EDITSTYLE.md 에디터
5. **Export** — 렌더링 + 다운로드

---

### 3.7 🧪 품질 강화

| 영역 | 현재 | 목표 |
|------|------|------|
| 테스트 | 197개 통과 | 300+ (edge case 커버리지) |
| 코덱 지원 | 일반적 H.264/H.265 | ProRes, AV1, VP9, 10-bit |
| 긴 영상 | 불안정 | 1시간+ 영상 안정 처리 |
| 자막 품질 | Whisper 기본 | 한국어 후처리 + 화자 분리 |
| 에러 복구 | 크래시 시 처음부터 | 체크포인트 기반 재개 |

---

## 4. 새 아키텍처

```
                    ┌─────────────────────────┐
                    │      User Interface      │
                    │  CLI / Desktop / Web UI  │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │      Agent Engine        │  ← NEW
                    │  Goal → Multi-step plan  │
                    │  Self-evaluation loop    │
                    │  EDITSTYLE.md aware      │
                    └────────────┬────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              ▼                  ▼                   ▼
     ┌────────────┐    ┌────────────┐    ┌──────────────┐
     │  Analyzer   │    │  Planner   │    │   Style      │
     │             │    │            │    │              │
     │ • Scenes    │    │ • LLM      │    │ • EditDNA    │
     │ • Whisper   │    │ • Rules    │    │ • EDITSTYLE  │
     │ • Quality   │    │ • Agent    │    │ • Extract    │
     │ • Engage    │    │            │    │ • Learn      │
     └──────┬─────┘    └──────┬─────┘    └──────┬───────┘
            │                 │                  │
            └────────────────▼──────────────────┘
                    ┌────────────────────┐
                    │      Editor        │
                    │  FFmpeg pipeline   │
                    │  + NLE export      │  ← NEW
                    └────────────────────┘
                             │
                    ┌────────▼────────┐
                    │   MCP Server    │  ← NEW
                    │  Tool exposure  │
                    └─────────────────┘
```

---

## 5. 빌드 로드맵

### Phase 5: Agent Mode + MCP (2-3주)

**Agent Mode:**
- [ ] `cutai/agent/` 모듈 — 목표 기반 멀티스텝 편집 루프
- [ ] `cutai agent` CLI 명령어
- [ ] 자기 평가 (결과물 분석 → 목표 대비 점수)
- [ ] 반복 편집 (--iterations N)
- [ ] EDITSTYLE.md 자동 적용 in agent loop

**MCP Server:**
- [ ] `cutai mcp-server` 명령어
- [ ] 8개 Tool 노출 (analyze, plan, edit, style-*, highlights, engagement, editstyle)
- [ ] Claude Code / Cursor 연동 테스트

### Phase 6: Performance + Quality (2주)

- [ ] MLX Whisper 통합 (Apple Silicon 가속)
- [ ] VideoToolbox 인코딩 (Metal)
- [ ] 병렬 장면 분석
- [ ] 분석 결과 캐시 (`.cutai-cache/`)
- [ ] 긴 영상 안정성 (1시간+)
- [ ] 한국어 자막 후처리
- [ ] 에러 체크포인트 + 재개

### Phase 7: NLE Export + Web UI (2-3주)

**NLE Export:**
- [ ] FCPXML export (Final Cut Pro)
- [ ] EDL export (범용)
- [ ] Premiere XML export

**Web UI:**
- [ ] React 프론트엔드 (데스크톱 컴포넌트 재사용)
- [ ] 타임라인 뷰 (장면 썸네일 + engagement)
- [ ] 채팅 편집 인터페이스
- [ ] EDITSTYLE.md 비주얼 에디터

### Phase 8: 생태계 + 커뮤니티 (ongoing)

- [ ] `awesome-editstyles` 레포 런칭 (10개+ 프리셋)
- [ ] EDITSTYLE.md 표준 문서 + 웹사이트
- [ ] 유튜버 채널 스타일 자동 추출 데모
- [ ] 커뮤니티 Style Hub (업로드/다운로드/별점)
- [ ] 플러그인 시스템 (커스텀 edit operation)
- [ ] Hacker News 2차 론칭 ("CutAI: The open-source agentic video editor")

---

## 6. 성공 지표 (갱신)

### 3개월 (v2 Phase 5-6)
- GitHub ⭐ 5,000+
- Agent Mode 작동 + MCP Server 연동
- 10분 영상 1분 이내 처리 (M3 Pro)
- awesome-editstyles 10개+ 프리셋

### 6개월 (v2 Phase 7-8)
- GitHub ⭐ 20,000+
- Web UI 공개 베타
- FCPXML/EDL export 안정화
- 커뮤니티 기여자 20명+
- EDITSTYLE.md를 다른 프로젝트에서 참조 시작

### 12개월
- GitHub ⭐ 50,000+
- "영상 편집의 DESIGN.md" = EDITSTYLE.md 인식 정착
- CutAI Agent가 프로 편집자의 러프컷 도구로 자리잡기
- 호스티드 버전 (Pro tier) 론칭 옵션 검토

---

## 7. 기술적 결정 사항

### 확정
| 결정 | 이유 |
|------|------|
| Python 유지 | ML 생태계 + FFmpeg 바인딩, 변경 불필요 |
| Typer CLI | 이미 16개 커맨드 안정적 |
| Pydantic v2 | 타입 시스템 완성도 높음 |
| EDITSTYLE.md 마크다운 | DESIGN.md 선례, AI 네이티브 |
| 로컬 퍼스트 | 시장 요구 + 차별화 |

### 검토 필요
| 항목 | 선택지 | 판단 시점 |
|------|--------|----------|
| Agent LLM | OpenAI / Anthropic / Ollama | Phase 5 시작 시 |
| Web UI 프레임워크 | React (재사용) vs Svelte (경량) | Phase 7 시작 시 |
| MCP 프로토콜 버전 | 현행 MCP spec 따르기 | Phase 5 |
| 수익화 모델 | 호스티드 Pro / 엔터프라이즈 / 후원 | 12개월 후 |

---

## 8. 리스크 & 대응 (갱신)

| 리스크 | 확률 | 대응 |
|--------|------|------|
| Wideframe 등 프로 도구가 오픈소스화 | 낮음 | 커뮤니티 + 생태계 선점이 해자 |
| Agent Mode 품질 불안정 | 높음 | 자기 평가 루프 + 사용자 승인 게이트 |
| MCP 표준 변경 | 중 | 추상화 레이어로 격리 |
| Apple Silicon 외 플랫폼 성능 | 중 | CUDA 지원 2순위로 추가 |
| EDITSTYLE.md 표준화 실패 | 중 | 자체 생태계로도 가치 있는 구조 |
| LLM 비용 (Agent 반복) | 높음 | 로컬 LLM 기본 + 클라우드 옵션 |

---

## 9. 즉시 실행 우선순위 (이번 주)

1. **Agent Mode 프로토타입** — `cutai/agent/engine.py` 기본 루프
2. **MCP Server 스캐폴드** — `cutai mcp-server` 진입점
3. **awesome-editstyles 레포 생성** — 기존 프리셋 2개 + 3개 추가
4. **README 업데이트** — EDITSTYLE.md 섹션 + Agent Mode 예고

---

_"촬영은 사람이, 편집은 에이전트가."_
