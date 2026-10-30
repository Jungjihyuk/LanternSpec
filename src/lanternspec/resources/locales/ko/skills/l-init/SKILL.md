---
name: l-init
description: LanternSpec 프로젝트 준비 — 질문 7개로 프로젝트 성격(신규/기존 · 인원 · 화면 유형 · 서버 · 지식 저장소 · 디자인 도구 · 프로젝트 종류)을 정하고 lantern.yaml · docs/ 폴더 · 템플릿 · MOC · 프로젝트 정의서 초안 · 개발 원칙 · git hook을 만든다. 프로젝트당 한 번, 성격이 바뀌면 다시 (1인→2인, 웹 추가 등). Use when setting up LanternSpec docs in a project or re-running after the project profile changed.
invocation: manual
argument-hint: "[바뀐 점 (다시 실행할 때)]"
---

# /l-init — 프로젝트에 맞는 문서 구조 만들기

**목적:** 질문 7개로 어떤 문서를 켜고 끌지, 어떤 개발 원칙을 따를지 정하고, 그 구조를 만든다. 형식(파일 · 폴더 · 번호)은 전부 `lantern` 명령이 만들고, 너는 묻고 · 판단하고 · 빈칸을 채운다.

먼저 `lantern --version`으로 CLI가 있는지 확인한다. 없으면 설치 안내(`uv tool install lanternspec`)만 하고 멈춘다.

## 0. 처음인가, 다시 실행인가
- `lantern.yaml`이 **없으면** → 아래 1단계부터.
- **있으면** → [다시 실행할 때](#다시-실행할-때)로 간다. 질문 7개를 다시 묻지 않는다.

## 1. 질문 7개 — 하나씩 묻고, 답은 모았다가 한 번에 쓴다
**묻는 법**
- 먼저 알 수 있는 것은 알아본 뒤 추천값으로 쓴다: 코드가 있나(`git ls-files`) · 언어(`lantern principles detect`) · 브랜치(`git branch`).
- **질문 하나에는 결정 하나만** 담는다. "있으면 A도, B도 알려 주세요"처럼 여러 답을 한 질문에 몰지 않는다 — 필요한 것은 따로 묻는다.
- 사람은 고르기만 하면 되게 선택지로 내고, 추천값에 표시한다.
- 경로 · 이름처럼 직접 써야 하는 답은 **찾을 수 있는 후보를 먼저 찾아 선택지로** 낸다. 후보가 있으면 질문 문장에 "맞는 게 없으면 맨 아래 칸에 직접 써 주세요"를 덧붙이고, **후보가 하나도 없으면** 선택지 질문 대신 평범한 메시지로 묻는다.
- 후보를 만들 수 없는 자유 답(한 문장 소개 · 팀원 이름)은 선택지 질문 대신 평범한 메시지로 묻는다 (AGENTS.md "묻는 법").
- 답을 받을 때마다 파일을 만들거나 명령을 실행하지 않는다. **모든 답을 모은 뒤** 2단계에서 한 번에 쓴다.
<!-- lantern:if tool=claude -->
- 질문 도구(AskUserQuestion)로 **한 번에 최대 4개씩** 묶어 보낸다. 화면에는 질문이 하나씩 나오고, 답은 한꺼번에 돌아온다.
  - 1회: 1 · 2 · 3 · 4번 (3번은 여러 개를 고를 수 있게)
  - 2회: 5 · 6번, 7번의 두 질문(종류 · 바깥 연결)
  - 3회: 앞 답에 따라 필요한 것만 — 프로젝트 이름 · 문서 올리기 · 기준 브랜치 · (team이면) 팀원 이름 · (external이면) API 문서
  - 4회: 5번에서 지식 저장소를 골랐을 때만 — 아래 "지식 저장소를 골랐으면"의 세 질문
<!-- lantern:endif -->
<!-- lantern:if !tool=claude -->
- 한 메시지에 **질문 하나만** 낸다. 답을 받으면 바로 다음 질문으로 넘어간다 (중간 요약 없이).
<!-- lantern:endif -->

**질문**
1. 🌱 새 프로젝트(greenfield)인가, 🏠 기존 코드가 있는 프로젝트(brownfield)인가? — 코드가 이미 있으면 brownfield를 추천
2. 몇 명이 하나? 1인(solo) / 2인 이상(team)
3. 무엇을 만드나? (화면 쪽, 여러 개 가능) 웹 · 데스크톱 · 모바일 · 없음
4. 백엔드(서버 쪽 코드와 데이터 저장)는 어떻게 하나? — 서버를 *어디에* 띄우는지가 아니라 서버 코드를 *직접 쓰는지*를 묻는다
   - 없음(none): 서버 없이 앱 · 웹 안에서만 동작. 데이터는 기기나 브라우저에 저장
   - 외부 서비스(external): Supabase · Firebase처럼 이미 만들어진 백엔드를 가져다 씀 — 서버 코드를 직접 쓰지 않음
   - 직접 만듦(custom): 서버 코드를 직접 작성 — AWS · GCP · Vercel · 사내 서버 등 어디에 띄우든 (로컬에서만 돌려도 여기)
5. 공부 노트를 모아 둔 지식 저장소가 있나? 없음 / Obsidian 볼트 / 일반 Markdown 폴더 — **종류만** 묻는다 (경로 · 쓰기 방식은 아래에서 따로)
6. 디자인 도구는? Claude Design / Figma / Canva / 없음 — Figma · Canva는 그 도구의 MCP 서버가 이 AI 도구에 연결돼 있어야 한다 (없으면 연결 방법을 안내하고, 연결 전까지는 내보낸 파일을 받는다)
7. 어떤 종류의 프로젝트인가? 스크립트 · 실험(script) / CLI 도구(cli) / 라이브러리 · 플러그인(library) / 서비스 — 웹 · 앱(service) / 데이터 · ML(data). 그리고 **바깥 도구 · 서비스에 붙나?** (AI 도구 · 결제 · 외부 API · 플러그인을 받는 구조 등) — 설계 원칙을 이 답으로 고른다
   - 언어는 묻기 전에 먼저 `lantern principles detect`로 알아본다. 알아본 것이 없으면(새 프로젝트) "무엇으로 만드나요? Python · TypeScript · Swift · Rust · Go"를 따로 묻는다
   - **규모는 묻지 않는다** — 코드 줄 수는 재고, 사람 수는 2번 답에서 나온다

**이어서 묻는다** (앞 답에 따라 필요한 것만)
- 프로젝트 이름 — 폴더 이름을 추천값으로
- "문서도 GitHub에 함께 올릴까요?" — 예(shared, 기본) / 아니요(local: 문서는 같은 저장소의 `docs-local` 브랜치에만, 원격에 안 올림. 혼자 보는 메모 · 공개 저장소에 어울림)
- 작업 브랜치를 머지할 기준 브랜치 — `git branch`로 보이는 main · dev를 선택지로
- 코드 주석(docstring · 주석)은 어떤 언어로 쓸까요? 한국어 / 영어 — 문서는 한국어로 만들고, 코드 안의 설명만 따로 정한다. 혼자 · 한국어 팀이면 한국어, 공개 오픈소스로 낼 거면 영어를 추천
- (2번이 team이면) 팀원 이름 — 후보를 만들 수 없으니 평범한 메시지로: "함께하는 사람 이름을 쉼표로 적어 주세요"
- (4번이 external이면) "API 명세 문서도 만들까요?" — 예면 `--extra api`

**지식 저장소를 골랐으면** (5번이 없음이 아닐 때만, 하나씩)
- **어디에 있나요?** — 먼저 후보를 찾는다: Obsidian이면 `.obsidian` 폴더가 있는 곳(`find ~ -maxdepth 4 -name .obsidian -type d`), Markdown 폴더면 문서 폴더 근처. 찾은 경로를 선택지로 내고(최대 3개), 못 찾으면 평범한 메시지로 "노트 폴더의 경로를 알려 주세요"라고 묻는다.
- **새 노트는 어떻게 만들까요?** — 승인하면 저장소에 바로 쓰기(direct, 추천) / 저장소는 건드리지 않고 초안 파일만 만들기(propose_only)
- **(저장소에 주제별로 나눈 폴더가 보일 때만) 그 분류도 함께 쓸까요?** (선택) — 먼저 저장소 맨 위 폴더를 훑어, 하위 폴더가 주제처럼 나뉜 폴더(예: `2. Study`)가 없으면 **이 질문은 건너뛴다**. 있으면 질문 문장에 뜻을 먼저 적는다: "모르는 기술은 부채 카드로 남고, 카드마다 주제가 하나 붙어요 (지금은 backend · frontend · data · ai · infra · 기타). 저장소에 주제별로 나눠 둔 폴더가 있는 것 같은데, 그 이름도 주제로 함께 쓸까요? 프로젝트 구조와는 상관없어요." 선택지는 찾은 폴더들과 "기본 주제만 쓰기"(추천).

답이 애매하면 추측하지 말고 다시 묻는다. 다 모았으면 답을 한 번에 요약해 보여 주고 2단계로 간다.

## 2. 프로필 쓰기 → 켜질 문서 계산 (스크립트)
```bash
lantern profile write --name "<이름>" --origin greenfield|brownfield --team solo|team [--members "지혁,민수"] \
  --clients web,mobile --server none|external|custom [--extra api] \
  [--knowledge "<지식 저장소 경로>" --knowledge-type obsidian|folder --knowledge-write direct|propose_only [--areas-from "2. Study"]] \
  --design claude-design|figma|canva|none --remote shared|local --base main \
  --kind script|cli|library|service|data --external yes|no [--languages python,typescript] --comment-language ko|en
lantern principles detect --write   # 코드 규모 · 언어 · 확인 명령(build.format · lint · typecheck)을 기록
lantern principles show             # 고른 설계 원칙 · 코드 컨벤션
lantern scaffold init --plan        # 만들 폴더 · 문서 목록 (아직 아무것도 안 만듦)
```
`principles show` 결과를 한두 줄로 알려 준다 (예: "CLI 도구 · 바깥 연결 → 단일 책임 · 확장 지점은 지킴, Python은 ruff · pyright").

**영역 (폴더마다 자기 규칙):** `lantern parts`가 자기 매니페스트를 가진 하위 폴더(예: `backend` · `frontend/apps/web`)를 후보로 보여 준다.
후보가 **둘 이상**이면 각각 근거와 함께 "이 폴더를 영역으로 둘까요?"를 한 번에 묻고, 답대로 `lantern parts add <폴더>` · `lantern parts ignore <폴더>`.
영역이 둘 이상이면 영역마다 `AGENTS.md`(그 언어의 컨벤션 · 그 폴더의 확인 명령)가 생기고, 루트 AGENTS.md에는 영역 지도가 남는다. 후보가 하나 이하면 묻지 않는다.

**도구 설정 파일:**
- 🏠 brownfield: `detect`가 찾은 **이미 쓰는 설정은 기록만** 한다 — 설정 파일(`pyproject.toml` · `.eslintrc` 등)을 바꾸거나 다른 도구로 갈아타자고 하지 않는다. 컨벤션에 있는데 설정이 없는 도구는 "들일까요?"만 묻는다.
- 🌱 greenfield: 컨벤션의 도구를 개발 의존성에 넣고(예: `uv add --dev ruff pyright` · `pnpm add -D @biomejs/biome typescript`) 설정(예: `pyproject.toml`의 `[tool.ruff]` · `[tool.pyright]`)을 만들지 **묻고, 승인하면** 한다. 개발 의존성에 있어야 CI에서도 같은 도구가 설치된다. 거절하면 `lantern profile set build.lint= build.typecheck=`로 비운다.
`--plan` 결과를 사용자에게 짧게 보여 준다 (예: "모바일 → 플랫폼 연동 · 배포 문서가 생겨요").

지식 저장소에 `--areas-from`이 있으면 `lantern knowledge areas`로 폴더 분류를 읽고, **부채 카드의 주제**(기본: backend · frontend · data · ai · infra · 기타)에 더할 것을 **제안만** 한다.
- 질문 문장에 무엇을 고르는지 먼저 적는다: "저장소에서 찾은 폴더 이름이에요. 부채 카드의 주제로 더하고 싶은 것을 골라 주세요. 부채 현황에서 주제별로 모르는 기술이 몇 개씩 쌓였는지 볼 때 쓰여요 (프로젝트 구조 · 노트 저장 위치와는 상관없어요)."
- 기본 분류와 겹치는 것(예: AI Engineering → ai)은 빼고 그 이유를 한 줄로 알린다. "기본 주제만 쓰기"를 늘 선택지에 둔다.
- 사용자가 고른 것만 `docs/<<folder.templates>>/_meta/enums.yaml`의 `area`에 넣는다 (3단계 scaffold 뒤).

## 3. 구조 만들기
- `local`을 골랐으면 **먼저** `lantern docs-mode local` (빈 문서 브랜치 · `.gitignore` · `.ignore` · push 막는 hook을 한 번에)
  실행 전에 한 줄로 알린다: "문서를 원격에 안 올리는 설정으로 바꾸면서, main에 설정 파일 3개(`.gitignore` · `.ignore` · `lantern.yaml`)를 커밋해요."
- 🏠 brownfield이고 `docs/`가 이미 있으면 **먼저** `lantern legacy adopt` (기존 문서를 `docs/<<folder.legacy>>/`로 `git mv` — 기록이 이어진다)
- 그다음 `lantern scaffold init`

## 4. 🌱 그린필드 — 짧은 인터뷰로 프로젝트 정의서 초안
`docs/<<folder.current>>/<<file.project_definition>>`의 `<<marker.required>>` 칸 세 개를 **차례로** 묻는다. 앞 답을 바탕으로 다음 칸의 후보를 만들어, 사람은 고르거나 고쳐 쓰기만 하게 한다.
1. **한 문장 소개** — 후보를 만들 수 없으니 질문 도구 대신 **평범한 메시지로** 묻고 예시를 하나 보여 준다: "이 프로젝트를 한 문장으로 소개해 주세요. (예: 혼자 쓰던 가계부를 친구와 함께 보는 앱)"
2. **주 사용자와 문제** — 소개를 바탕으로 후보 2~3개를 만들어 고르게 한다.
3. **목표** — 소개 · 사용자를 바탕으로 **확인할 수 있는 목표 후보 3~4개**를 만들어 여러 개 고르게 한다 (예: "친구 초대 후 함께 쓴 지출이 한 화면에 보인다"). 지금 정하기 어려우면 **"나중에 정하기"**를 고를 수 있다.

- 고른 답을 빈칸에 채운다. "나중에 정하기"나 모르는 칸은 `<<marker.unknown>>`로 둔다 — `lantern status`의 열린 질문에 남아 잊히지 않는다.
- 선택 칸은 비어 있어도 된다.

## 5. 🏠 브라운필드 — 채우기 → 연결하기 → 빈칸 묻기
1. **채우기:** 코드(무엇이 있나: 사실) + `<<folder.legacy>>/`(왜: 배경)를 읽고 `<<folder.current>>`의 초안을 채운다 — 시스템 구조 · 기능 목록 · 데이터 · (있으면) API.
   - 데이터: SQL 마이그레이션이 있으면 `lantern dbml from-sql <마이그레이션 폴더> --out "docs/<<folder.current>>/<<folder.data>>/schema.dbml"` → `lantern dbml render`. **마이그레이션 · 실제 DB가 기준**이다.
   - 각 현재 상태 문서 frontmatter에 관련 코드와 확인 시점을 적는다: `lantern meta set "<문서>" 'code=[src/auth, src/api]' checked_commit=$(git rev-parse --short HEAD)`
2. **연결하기:** 채운 내용마다 `출처: [[<<folder.legacy>>/…]]` 링크를 단다.
3. **기존 문서 지도:** `<<folder.legacy>>/<<file.legacy_map>>` 표에 문서마다 무슨 내용 · 아직 맞나 · 갈래 · 새 위치를 채운다. 갈래는 네가 추천하고 사용자는 확인만 한다:
   - 🧽 흡수 — 지금도 맞는 내용 → 핵심만 `<<folder.current>>`에 + 출처 링크
   - 🗄 보관 — 지난 기록(회의록 · 옛 기획 · 끝난 작업) → 링크만
   - 🚚 옮기기 — 계속 쓸 문서 → 원할 때 `/l-template migrate "<<folder.legacy>>/….md"`
4. **빈칸 묻기:** 필수 칸만 · 짐작되면 "이게 맞나요?"로 · 한 문서의 질문은 묶어서 · "모름"은 `<<marker.unknown>>`.
5. **덤:** `lantern legacy todos`로 기존 문서의 TODO · 나중에 할 것을 모아 아이디어 후보로 보여 준다. 사용자가 고른 것만 `/l-idea`로 기록한다.

## 6. git hook · CI · Obsidian
"커밋할 때 작업 ID · 스키마 기록 · 양식을 검사하는 git hook을 설치할까요? (기본은 경고만)" → 예면 `lantern hooks install`.
2인 이상(team)이면 한 번 더: "처음부터 막을까요?" → 예면 `lantern profile set git.hooks=block`.
(구조 실수 — 문서 저장 방식 규칙 — 는 이 값과 상관없이 항상 막는다.)

`git remote -v`에 github.com이 있으면 이어서 묻는다: "GitHub에서도 검사할까요? push할 때마다 GitHub이 양식 검사 · 린트 · 타입 검사 · 테스트를 대신 돌려요 (CI)." → 예면 `lantern install --ci`.
워크플로에 이 프로젝트 언어의 도구 준비 단계(uv · pnpm 설치 등)가 함께 들어간다. 나중에 끄려면 `lantern install --no-ci`.

이어서 묻는다: "문서를 Obsidian으로 볼 때 쓰는 권장 플러그인(Dataview · Metadata Menu)을 같이 받아 둘까요? 상태 · 종류를 고르는 메뉴와 할 일 표시가 바로 동작해요." (추천: 예) → 예면 `lantern obsidian plugins`.
- 받은 플러그인 코드는 git에 올라가지 않는다 (`docs/.obsidian/.gitignore`). 팀원은 같은 명령으로 받는다.
- 받지 못하면(인터넷 없음 등) 실패로 멈추지 말고, Obsidian의 커뮤니티 플러그인에서 두 플러그인을 직접 설치하면 된다고 알린다.

## 7. 작업 방식 추천 · 공통 마무리
`lantern harness suggest`로 프로젝트 크기에 맞는 AI 작업 방식(하네스 · 루프 · 그래프)을 한 줄로 알려 주고, 사용자가 원하면 `--apply` 뒤 `lantern upgrade`.
```bash
lantern close l-init
```
검사 결과의 ✖ 오류는 고치고, ⚠ 필수 빈칸은 무엇이 남았는지 알려 준다. 끝으로 3줄 보고: 만든 것 · 남은 빈칸 · 다음 (`/l-idea` 또는 `/l-plan`, 브라운필드는 현황 확인 뒤 `/l-idea`).

---

## 다시 실행할 때
1. `lantern profile show`로 지난 답을 보여 주고 **"바뀐 게 있나요?"**만 묻는다.
2. 바뀐 값을 `lantern profile set key=value …`로 고친다 (예: `project.team=team 'project.members=[지혁, 민수]'`, `'project.clients=[mobile, web]'`).
3. `lantern scaffold init --plan`으로 **새로 켜질 문서를 먼저 알려 주고** 되묻는다: "웹이 추가되면 웹 화면 · 웹 배포 칸이 생겨요. 추가할까요?"
4. 추가하기로 한 문서에 필요한 질문만 이어서 한다 (`--plan` 출력의 "물을 것" 참고: 웹 → 배포 방식, 팀 → 팀원 이름).
5. `lantern scaffold init` — 새 문서만 만들고 기존 문서는 그대로. 필요 없어진 문서는 지우지 않고 "<<current_status.inactive>>"으로 표시된다. 이미 있는 문서에 새 유형 칸(예: `## 웹`)이 필요하면 해당 문서에 칸을 추가한다.
6. 문서 저장 방식(shared ↔ local)은 여기서 바꾸지 않는다 → `lantern docs-mode local|shared`.
7. `idea.capture` 같은 스킬 동작 값이나 프로젝트 종류(`project.kind` · `project.external` · `project.languages`)가 바뀌었으면 `lantern upgrade` (스킬 · AGENTS.md의 개발 원칙 · 개발 원칙 문서를 다시 만든다).
8. 공통 마무리 `lantern close l-init`.
