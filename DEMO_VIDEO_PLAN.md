# CutAI 데모 영상 계획

## 목적
EST(Edit Style Transfer)가 실제로 동작하는 걸 보여주는 30~60초 데모

## 시나리오

### 데모 A: "같은 영상, 다른 스타일" (메인 데모)
1. 원본 영상 보여주기 (편집 안 된 vlog 30초)
2. 스타일 A 적용 (cinematic — 느린 페이싱, 따뜻한 색감, 시네마틱 자막)
3. 스타일 B 적용 (fast-vlog — 빠른 컷, 밝은 색감, 팝 자막)
4. 나란히 비교

### 데모 B: "유튜버 스타일 추출" (킬러 데모)
1. 유명 유튜버 영상에서 `cutai style-extract` 실행
2. Edit DNA YAML 보여주기 (터미널)
3. 내 영상에 적용 → 결과

### 데모 C: "한 줄 편집" (보조)
1. `cutai edit vlog.mp4 -i "remove boring parts, add subtitles"`
2. 터미널 실행 → 결과 재생

## 제작 방법
- 터미널 녹화 (asciinema 또는 screen recording)
- before/after 비교는 영상 병렬 배치
- 배경음악: 라이선스 프리 로파이

## 필요한 소스 영상
- 편집 안 된 vlog 원본 (1~2분 분량)
- 테스트용 레퍼런스 영상 (public domain 또는 CC)

## 배포
- GitHub README에 임베드
- 랜딩 페이지 히어로
- HN/Reddit 포스트 링크
- YouTube에도 업로드 (SEO)
