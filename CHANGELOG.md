# 바뀐 점

이 프로젝트의 바뀐 점을 버전마다 적는다.
형식은 [Keep a Changelog](https://keepachangelog.com/ko/1.1.0/), 버전은 [유의적 버전](https://semver.org/lang/ko/)을 따른다.

## [Unreleased]

## [0.1.0] - 2026-10-27

첫 배포.

### 추가
- **`lantern` CLI** — 형식은 스크립트가 맡는다: 문서 만들기(`scaffold`) · ID 발급 · frontmatter · 양식 검사(`check`) ·
  MOC 지도(`map`) · 보고(`report` · `status`) · 문서와 코드가 맞는지 확인(`scan` · `sync`) · 설치 점검(`doctor`)
- **스킬 13개** — `/l-init` · `/l-idea` · `/l-plan` · `/l-design` · `/l-task` · `/l-build` · `/l-learn` · `/l-report` ·
  `/l-template` · `/l-check` · `/l-sync` · `/l-map` · `/l-adr`. 스킬 원본 한 벌을 `lantern.yaml` 값으로 채워 도구마다 설치
- **AI 도구 3종** — Claude Code · Codex · Antigravity CLI에 스킬 · `AGENTS.md` 규칙 · 에이전트 hook · MCP 서버를 설치
  (`lantern install` · `lantern upgrade`, 사용자가 고친 파일은 덮어쓰지 않음)
- **문서 양식 24종** — 프로젝트 성격(신규/기존 · 인원 · 화면 · 서버 · 지식 저장소)에 따라 켜지는 문서가 정해진다.
  양식 버전 관리 · 다듬기 · 옮기기(`template`), 상태 · 종류 이름은 `enums.yaml` 한 곳에서 (`enums rename`)
- **작업 흐름** — 아이디어 → 기획 → 설계(승인 게이트 · DBML · 화면 시안) → 할 일(의존 · 병렬 `[P]`) → 구현(작업 브랜치 ·
  worktree · 증거 기록 · 현재 상태 반영)
- **모르는 기술 관리** — 지식 저장소 연결기(Obsidian · 일반 Markdown 폴더)와 부채 장부
  (이해 · 역량 · 기술), MCP 서버(`lantern mcp`)
- **문서와 코드가 어긋나지 않게** — git hook(작업 ID · 스키마 기록 · 양식 · 문서 저장 방식), 에이전트 hook(대화 시작 요약 · 문서 쓰면
  바로 검사 · 실행 기록 · 동기화 권유 · 대화 압축 전 진행 상황 저장 · 기술 질문 · 아이디어 감지), GitHub Actions CI
  (`install --ci`: 언어별 도구 준비 포함)
- **문서 저장 방식** — 코드와 함께 올리기(shared) 또는 원격에 올리지 않기(local, `docs-mode`)
- **개발 원칙 · 코드 컨벤션** — 프로젝트 종류 · 바깥 연결 · 규모로 설계 원칙을, 언어(Python · TypeScript · Swift ·
  Rust · Go)와 규모로 코드 컨벤션을 기준표대로 골라 `AGENTS.md`와 `개발 원칙.md`에 넣는다 (`principles`, `lint`)
- **작업 방식 · 평가** — 하네스 · 루프 · 그래프 추천(`harness suggest`), 실행 기록으로 스킬 · 모델 · 설정 비교(`eval`)

[Unreleased]: https://github.com/Jungjihyuk/LanternSpec/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Jungjihyuk/LanternSpec/releases/tag/v0.1.0
