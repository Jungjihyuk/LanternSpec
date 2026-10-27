# 바뀐 점

[English](https://github.com/Jungjihyuk/LanternSpec/blob/main/CHANGELOG.md) · **한국어**

이 프로젝트의 바뀐 점을 버전마다 적는다.
형식은 [Keep a Changelog](https://keepachangelog.com/ko/1.1.0/), 버전은 [유의적 버전](https://semver.org/lang/ko/)을 따른다.

## [Unreleased]

## [0.1.1] - 2026-10-28

업그레이드: `uv tool upgrade lanternspec` → 프로젝트마다 `lantern upgrade` (스킬 · AGENTS.md 규칙 · Obsidian 설정을 새로 맞춘다)

### 추가
- **Obsidian 볼트 설정** — `docs/`를 Obsidian으로 열면 문서 종류마다 그 종류의 상태 · 종류 · 주제만 고르는 메뉴(Metadata Menu, `enums.yaml`에서 만들어짐), 문서 단계별 폴더 색, callout · 인용문 모양이 적용된다. 이미 있던 `.obsidian` 설정은 그대로 둔다
- **`lantern obsidian plugins`** — 권장 플러그인(Dataview · Metadata Menu)의 최신 공식 배포 파일을 받는다. `/l-init`이 받을지 묻는다. 플러그인 코드와 창 배치는 git에 올라가지 않는다
- **설치 뒤 안내** — `lantern install`이 AI 도구를 여는 명령과 `/l-init`을 부르는 법을 알려 주고, 이 컴퓨터에 있지만 설정하지 않은 AI 도구가 있으면 `--tools`로 더하는 법을 알려 준다

### 바뀜
- **`/l-init` 질문** — 질문 하나에 결정 하나만 담는다. 지식 저장소는 종류만 먼저 묻고 경로 · 쓰기 방식 · 주제 폴더는 따로 묻는다. 경로 · 이름은 후보를 찾아 선택지로 낸다
- **백엔드 질문** — "서버가 필요한가" 대신 "서버 코드를 직접 쓰는가"로 묻는다 (AWS · GCP · Vercel에 띄워도 직접 만듦, Supabase · Firebase는 외부 서비스)
- **프로젝트 정의서 인터뷰** — 사용자와 목표는 AI가 만든 후보에서 고른다. 목표는 "나중에 정하기"를 고를 수 있다 (열린 질문으로 남음)
- **AI가 말하는 방식** — AGENTS.md 블록에 두 가지 규칙을 더했다: 사용자에게는 `project.language`(한국어)로 말한다, "직접 입력" 같은 빈 선택지를 만들지 않는다
- **부채 카드 "영역" → "주제"** — 화면에 보이는 이름만 바뀐다. 저장 키(`area`)와 `--area` 옵션은 그대로
- **명세 번호 대신 이름** — 설치 출력 · git hook 경고 · 에이전트 hook 메시지 · `lantern.yaml` 주석 · 스킬에서 `H-4~H-10` 같은 내부 번호를 없애고 무엇을 검사하는지로 부른다 (커밋 메시지 · 스키마 기록 · 문서 양식 · 기술 질문 · 아이디어)

### 고침
- `/l-init` 마무리 보고가 영어로 나오던 문제
- 터미널에서 기존 프로젝트 아이콘(🏚)이 뒤 글자를 덮던 문제 — 🏠으로 바꿈

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

[Unreleased]: https://github.com/Jungjihyuk/LanternSpec/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/Jungjihyuk/LanternSpec/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/Jungjihyuk/LanternSpec/releases/tag/v0.1.0
