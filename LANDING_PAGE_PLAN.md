# CutAI 랜딩 페이지 기획

## URL
cutai.dev (또는 cutai.app)

## 핵심 메시지
**"Learn any editing style. Apply it to your videos."**

---

## 섹션 구성

### 1. Hero
- 헤드라인: **"Edit videos by telling it what you want."**
- 서브: "One sentence → scene detection, smart cuts, auto subtitles, color grading. Plus: learn any video's editing style and reuse it."
- CTA: `pip install cutai` + GitHub 버튼 + Desktop Download
- 히어로 영상/GIF: before(원본) → after(스타일 적용) 비교

### 2. How Edit Style Transfer works (3단계)
```
① Pick a reference     → 좋아하는 영상 하나 골라
② Extract Edit DNA     → 편집 패턴을 자동 분석
③ Apply to your video  → 내 영상에 그 스타일 적용
```
- 각 단계 GIF/스크린샷
- Edit DNA YAML 예시 보여주기 (코드블록)

### 3. Edit DNA가 캡처하는 것
- Cut Rhythm: 장면 길이, 페이싱 곡선
- Visual Style: 색온도, 밝기, 채도
- Subtitles: 자막 스타일, 위치
- Audio: BGM 믹싱, 볼륨 밸런스
- Transitions: 컷 타입, 빈도

### 4. Style Learn (여러 영상에서 학습)
- "Watch 3 videos → blend into one style"
- 코드 예시: `cutai style-learn v1.mp4 v2.mp4 v3.mp4 -o brand.yaml`

### 5. 그 외 기능 (간략하게)
- Natural language editing
- Auto subtitles (Whisper)
- Smart highlights
- 100% local, no cloud
- Korean + English

### 6. Desktop App
- macOS 스크린샷
- Download DMG 버튼

### 7. Open Source
- MIT License
- GitHub Stars 카운터
- "Star us on GitHub" CTA

### 8. Footer
- GitHub / Discord / Twitter
- `pip install cutai`

---

## 기술 스택 (랜딩 페이지)
- Next.js + Tailwind (가볍고 빠르게)
- Vercel 배포
- 도메인: cutai.dev 또는 cutai.app

## 디자인 톤
- 다크 테마 (영상 편집 도구 느낌)
- 모노스페이스 코드 블록
- 비교 영상 GIF가 핵심
