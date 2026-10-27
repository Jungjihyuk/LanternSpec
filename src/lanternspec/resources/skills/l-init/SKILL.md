---
name: l-init
description: LanternSpec 프로젝트 준비 — 질문 7개로 프로젝트 성격(신규/기존 · 인원 · 화면 유형 · 서버 · 지식 저장소 · 디자인 도구 · 프로젝트 종류)을 정하고 lantern.yaml · docs/ 폴더 · 템플릿 · MOC · 프로젝트 정의서 초안 · 개발 원칙 · git hook을 만든다. 프로젝트당 한 번, 성격이 바뀌면 다시 (1인→2인, 웹 추가 등). Use when setting up LanternSpec docs in a project or re-running after the project profile changed.
invocation: manual
argument-hint: "[바뀐 점 (다시 실행할 때)]"
---

# /l-init — 프로젝트에 맞는 문서 구조 만들기

**목적:** 질문 7개로 어떤 문서를 켜고 끌지, 어떤 개발 원칙을 따를지 정하고, 그 구조를 만든다. 형식(파일 · 폴더 · 번호)은 전부 `lantern` 명령이 만들고, 너는 묻고 · 판단하고 · 빈칸을 채운다.

먼저 `lantern --version`으로 CLI가 있는지 확인한다. 없으면 설치 안내(`uv tool install <lanternspec 저장소 경로>` — PyPI 배포 뒤에는 `pipx install lanternspec`)만 하고 멈춘다.

## 0. 처음인가, 다시 실행인가
- `lantern.yaml`이 **없으면** → 아래 1단계부터.
- **있으면** → [다시 실행할 때](#다시-실행할-때-i-01)로 간다. 질문 7개를 다시 묻지 않는다.

## 1. 질문 7개 (한 메시지에 번호로 묶어서, 추천값과 함께)
1. 🌱 새 프로젝트(greenfield)인가, 🏚 기존 코드가 있는 프로젝트(brownfield)인가? — 코드가 이미 있으면 brownfield를 추천
2. 몇 명이 하나? 1인(solo) / 2인 이상(team) — team이면 팀원 이름도
3. 무엇을 만드나? (화면 쪽, 여러 개 가능) 웹 · 데스크톱 · 모바일 · 없음
4. 서버가 필요한가? 없음(none) / 외부 서비스 Supabase · Firebase 등(external) / 직접 구축(custom)
   - external이면: "API 명세 문서도 켤까요?" (필요하면 켜짐 → `--extra api`)
5. 지식 저장소는? (없음 가능) Obsidian 폴더 · MY_BRAIN(`.my-wiki/document_cards.jsonl` 카드 색인이 있는 볼트) · 아무 Markdown 폴더 · Notion(부모 페이지 ID + 환경 변수 `NOTION_TOKEN`). 있으면: 노트를 승인 후 바로 쓸까(direct), 초안 파일만 만들까(propose_only)? 영역 분류 폴더(예: `2. Study`)가 있나?
6. 디자인 도구는? Claude Design / Figma / Canva / 없음 — Figma · Canva는 그 도구의 MCP 서버가 이 AI 도구에 연결돼 있어야 한다 (없으면 연결 방법을 안내하고, 연결 전까지는 내보낸 파일을 받는다)
7. 어떤 종류의 프로젝트인가? 스크립트 · 실험(script) / CLI 도구(cli) / 라이브러리 · 플러그인(library) / 서비스 — 웹 · 앱(service) / 데이터 · ML(data). 그리고 **바깥 도구 · 서비스에 붙나?** (AI 도구 · 결제 · 외부 API · 플러그인을 받는 구조 등) — 설계 원칙을 이 답으로 고른다
   - 언어는 묻기 전에 먼저 `lantern principles detect`로 알아본다. 알아본 것이 없으면(새 프로젝트) "무엇으로 만드나요? Python · TypeScript · Swift · Rust · Go"를 함께 묻는다
   - **규모는 묻지 않는다** — 코드 줄 수는 재고, 사람 수는 2번 답에서 나온다

같은 메시지에 함께 묻는다:
- 프로젝트 이름
- "문서도 GitHub에 함께 올릴까요?" — 예(shared, 기본) / 아니요(local: 문서는 같은 저장소의 `docs-local` 브랜치에만, 원격에 안 올림. 혼자 보는 메모 · 공개 저장소에 어울림)
- 작업 브랜치를 머지할 기준 브랜치 (`git branch`로 보이는 main · dev 중 추천)

답이 애매하면 추측하지 말고 다시 묻는다.

## 2. 프로필 쓰기 → 켜질 문서 계산 (스크립트)
```bash
lantern profile write --name "<이름>" --origin greenfield|brownfield --team solo|team [--members "지혁,민수"] \
  --clients web,mobile --server none|external|custom [--extra api] \
  [--knowledge "<경로 · Notion 부모 페이지 ID>" --knowledge-type obsidian|my_brain|folder|notion --knowledge-write direct|propose_only [--areas-from "2. Study"]] \
  --design claude-design|figma|canva|none --remote shared|local --base main \
  --kind script|cli|library|service|data --external yes|no [--languages python,typescript]
lantern principles detect --write   # 코드 규모 · 언어 · 확인 명령(build.format · lint · typecheck)을 기록
lantern principles show             # 고른 설계 원칙 · 코드 컨벤션
lantern scaffold init --plan        # 만들 폴더 · 문서 목록 (아직 아무것도 안 만듦)
```
`principles show` 결과를 한두 줄로 알려 준다 (예: "CLI 도구 · 바깥 연결 → 단일 책임 · 확장 지점은 지킴, Python은 ruff · pyright").

**도구 설정 파일 (I-05 ⑤):**
- 🏚 brownfield: `detect`가 찾은 **이미 쓰는 설정은 기록만** 한다 — 설정 파일(`pyproject.toml` · `.eslintrc` 등)을 바꾸거나 다른 도구로 갈아타자고 하지 않는다. 컨벤션에 있는데 설정이 없는 도구는 "들일까요?"만 묻는다.
- 🌱 greenfield: 컨벤션의 도구를 개발 의존성에 넣고(예: `uv add --dev ruff pyright` · `pnpm add -D @biomejs/biome typescript`) 설정(예: `pyproject.toml`의 `[tool.ruff]` · `[tool.pyright]`)을 만들지 **묻고, 승인하면** 한다. 개발 의존성에 있어야 CI에서도 같은 도구가 설치된다. 거절하면 `lantern profile set build.lint= build.typecheck=`로 비운다.
`--plan` 결과를 사용자에게 짧게 보여 준다 (예: "모바일 → 플랫폼 연동 · 배포 문서가 생겨요").

지식 저장소에 `--areas-from`이 있으면 `lantern knowledge areas`로 폴더 분류를 읽고, 기본 영역(backend · frontend · data · ai · infra)에 **추가할 영역을 제안만** 한다. 사용자가 고른 것만 `docs/0. 템플릿/_meta/enums.yaml`의 `area`에 넣는다 (2단계 scaffold 뒤).

## 3. 구조 만들기
- `local`을 골랐으면 **먼저** `lantern docs-mode local` (빈 문서 브랜치 · `.gitignore` · `.ignore` · push 막는 hook을 한 번에)
- 🏚 brownfield이고 `docs/`가 이미 있으면 **먼저** `lantern legacy adopt` (기존 문서를 `docs/5. 기존 문서/`로 `git mv` — 기록이 이어진다)
- 그다음 `lantern scaffold init`

## 4. 🌱 그린필드 — 짧은 인터뷰로 프로젝트 정의서 초안
`docs/3. 현재 상태/프로젝트 정의서.md`의 `(필수)` 칸만 묻는다: 한 문장 소개 · 주 사용자와 문제 · 목표. 한 번에 묶어서 묻고, 답을 빈칸에 채운다. 모르는 칸은 `❓ 확인 필요`로 둔다. 선택 칸은 비어 있어도 된다.

## 5. 🏚 브라운필드 — 채우기 → 연결하기 → 빈칸 묻기 (I-02)
1. **채우기:** 코드(무엇이 있나: 사실) + `5. 기존 문서/`(왜: 배경)를 읽고 `3. 현재 상태`의 초안을 채운다 — 시스템 구조 · 기능 목록 · 데이터 · (있으면) API.
   - 데이터: SQL 마이그레이션이 있으면 `lantern dbml from-sql <마이그레이션 폴더> --out "docs/3. 현재 상태/데이터/schema.dbml"` → `lantern dbml render`. **마이그레이션 · 실제 DB가 기준**이다.
   - 각 현재 상태 문서 frontmatter에 관련 코드와 확인 시점을 적는다: `lantern meta set "<문서>" 'code=[src/auth, src/api]' checked_commit=$(git rev-parse --short HEAD)`
2. **연결하기:** 채운 내용마다 `출처: [[5. 기존 문서/…]]` 링크를 단다.
3. **기존 문서 지도:** `5. 기존 문서/기존 문서 지도.md` 표에 문서마다 무슨 내용 · 아직 맞나 · 갈래 · 새 위치를 채운다. 갈래는 네가 추천하고 사용자는 확인만 한다:
   - 🧽 흡수 — 지금도 맞는 내용 → 핵심만 `3. 현재 상태`에 + 출처 링크
   - 🗄 보관 — 지난 기록(회의록 · 옛 기획 · 끝난 작업) → 링크만
   - 🚚 옮기기 — 계속 쓸 문서 → 원할 때 `/l-template migrate "5. 기존 문서/….md"`
4. **빈칸 묻기:** 필수 칸만 · 짐작되면 "이게 맞나요?"로 · 한 문서의 질문은 묶어서 · "모름"은 `❓ 확인 필요`.
5. **덤:** `lantern legacy todos`로 기존 문서의 TODO · 나중에 할 것을 모아 아이디어 후보로 보여 준다. 사용자가 고른 것만 `/l-idea`로 기록한다.

## 6. git hook · CI
"커밋할 때 작업 ID · 스키마 기록 · 양식을 검사하는 git hook을 설치할까요? (기본은 경고만)" → 예면 `lantern hooks install`.
2인 이상(team)이면 한 번 더: "처음부터 막을까요?" → 예면 `lantern profile set git.hooks=block`.
(구조 실수 — 문서 저장 방식 규칙 — 는 이 값과 상관없이 항상 막는다.)

`git remote -v`에 github.com이 있으면 이어서 묻는다: "GitHub에서도 검사할까요? push할 때마다 GitHub이 양식 검사 · 린트 · 타입 검사 · 테스트를 대신 돌려요 (CI)." → 예면 `lantern install --ci`.
워크플로에 이 프로젝트 언어의 도구 준비 단계(uv · pnpm 설치 등)가 함께 들어간다. 나중에 끄려면 `lantern install --no-ci`.

## 7. 작업 방식 추천 · 공통 마무리
`lantern harness suggest`로 프로젝트 크기에 맞는 AI 작업 방식(하네스 · 루프 · 그래프)을 한 줄로 알려 주고, 사용자가 원하면 `--apply` 뒤 `lantern upgrade`.
```bash
lantern close l-init
```
검사 결과의 ✖ 오류는 고치고, ⚠ 필수 빈칸은 무엇이 남았는지 알려 준다. 끝으로 3줄 보고: 만든 것 · 남은 빈칸 · 다음 (`/l-idea` 또는 `/l-plan`, 브라운필드는 현황 확인 뒤 `/l-idea`).

---

## 다시 실행할 때 (I-01)
1. `lantern profile show`로 지난 답을 보여 주고 **"바뀐 게 있나요?"**만 묻는다.
2. 바뀐 값을 `lantern profile set key=value …`로 고친다 (예: `project.team=team 'project.members=[지혁, 민수]'`, `'project.clients=[mobile, web]'`).
3. `lantern scaffold init --plan`으로 **새로 켜질 문서를 먼저 알려 주고** 되묻는다: "웹이 추가되면 웹 화면 · 웹 배포 칸이 생겨요. 추가할까요?"
4. 추가하기로 한 문서에 필요한 질문만 이어서 한다 (`--plan` 출력의 "물을 것" 참고: 웹 → 배포 방식, 팀 → 팀원 이름).
5. `lantern scaffold init` — 새 문서만 만들고 기존 문서는 그대로. 필요 없어진 문서는 지우지 않고 "<<current_status.inactive>>"으로 표시된다. 이미 있는 문서에 새 유형 칸(예: `## 웹`)이 필요하면 해당 문서에 칸을 추가한다.
6. 문서 저장 방식(shared ↔ local)은 여기서 바꾸지 않는다 → `lantern docs-mode local|shared`.
7. `idea.capture` 같은 스킬 동작 값이나 프로젝트 종류(`project.kind` · `project.external` · `project.languages`)가 바뀌었으면 `lantern upgrade` (스킬 · AGENTS.md의 개발 원칙 · 개발 원칙 문서를 다시 만든다).
8. 공통 마무리 `lantern close l-init`.
