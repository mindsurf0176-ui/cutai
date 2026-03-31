# CutAI Release Closeout Checklist

## 1) Version / State
- [ ] 릴리스 버전 확정: `vX.Y.Z` 태그/브랜치 점검
- [ ] 대상 브랜치(`master`/릴리스 브랜치) 기준 커밋 해시 기록
- [ ] 배포 대상 환경(dev / staging / prod) 및 차등 체크리스트 확인

## 2) Pre-release Preparation
- [ ] 릴리스 노트 초안 작성 및 변경사항 요약 검토
- [ ] 긴급 이슈/미해결 이슈 상태 재확인 (blocker 존재 시 마감 연기)
- [ ] 의존성 업데이트 알림 및 보안 패치 반영 상태 확인

## 3) Docs / Scripts Verification
- [ ] `README`/`CHANGELOG`/운영 문서에 버전·변경사항 반영
- [ ] 배포 스크립트(`release`, `build`, `notarize`) 최신화 여부 확인
- [ ] 릴리스 체크포인트 스크립트가 실패 시 종료하도록 구성
- [ ] `desktop/RELEASE_CLOSEOUT_CHECKLIST.md` 포함 여부 및 체크 항목 최신화

## 4) Tests
- [ ] `pnpm test` 통과
- [ ] `cargo test` 실행 전 `gen/backend/.gitignore` 플레이스홀더 존재 여부 확인
- [ ] `cargo test` 통과 (`placeholder` 누락 시 즉시 중단)
- [ ] `pytest` 통과 (필요 시 통합/회귀 테스트 포함)
- [ ] 테스트 실패 재현 로그 보존 및 실패 원인 공유

## 5) Build
- [ ] 전체 릴리스 빌드 성공
- [ ] 산출물 아티팩트 해시/버전 메타데이터 저장
- [ ] 주요 실행 경로(메인/CLI/desktop) 동작 스모크 테스트 수행

## 6) Verify / Notarize
- [ ] 바이너리 서명 정책(필요 시) 재확인
- [ ] notarize 실행 및 결과 저장(로그/receipt)
- [ ] 최종 번들 무결성 및 설치 테스트 수행

## 7) Final Go / No-go
- [ ] Critical 기능/보안/성능 이슈 없음 (미해결치료 불가 시 No-go)
- [ ] 롤백 플랜 및 긴급 핫픽스 절차 준비 완료
- [ ] Release Owner 승인(Go/No-go) 완료

## 8) Remaining External / Manual Items
- [ ] 앱스토어/배포 채널 메타데이터 등록
- [ ] 운영팀/CS에게 릴리스 노트 및 대응 메뉴얼 전달
- [ ] 모니터링 대시보드 임계치(알람/로그) 확인 및 담당자 지정
- [ ] 고객 커뮤니케이션 타이밍 예약

## Release Readiness Quick Check (10 lines)
- [ ] 버전·태그가 확정되었는가?
- [ ] 대상 브랜치가 정확한가?
- [ ] 문서 최신 반영이 완료되었는가?
- [ ] `pnpm test`가 통과했는가?
- [ ] `gen/backend/.gitignore` 플레이스홀더가 준비되었는가?
- [ ] `cargo test`가 통과했는가?
- [ ] `pytest`가 통과했는가?
- [ ] 빌드 산출물이 완성되었는가?
- [ ] notarize/서명/무결성 검증이 완료되었는가?
- [ ] Go/No-go 최종 승인과 외부 수작업 항목이 해결되었는가?
