# LanternSpec

> **Light up the unknowns. See how far you've come.**
> Spec-driven development for agentic software engineering.

사람은 팀장, AI는 팀원, 문서는 업무 보고서다. 아이디어를 말하면 **기획서 → 설계서 → 할 일 → 코드**까지
익숙한 개발 문서 양식으로 이어지고 Obsidian에서 한눈에 보인다. 그 과정에서 모르는 기술이 나오면
**내 지식 저장소와 비교해서** 복습할 것과 새로 공부할 것을 알려 준다.

| | 다들 하는 것 | LanternSpec이 강점을 두는 것 |
|---|---|---|
| 문서 | 명세를 잘 쓰고 검증한다 | **사람이 읽기 쉬운 문서 키트** — 옛 개발 문서 흐름 그대로라 신입도 바로 읽는다 |
| 사람 | 사람이 병목이니 덜 개입하게 한다 | **이해 부채를 줄인다** — AI가 만든 걸 이해하지 못한 채 넘어가지 않게 지식 저장소와 연결한다 |

## 설치

```bash
uv tool install ~/Documents/GitHub/lanternspec   # PyPI 배포 전: 이 저장소에서 설치 (또는 pipx install <경로>)
cd my-project
lantern install                  # Claude Code (기본). 여러 도구: --tools claude,codex,antigravity
```

`lantern install`은 플러그인이 아니라 **프로젝트 폴더에 직접** 스킬을 써 넣는다 (Claude Code `.claude/skills/l-*`,
Codex · Antigravity CLI `.agents/skills/l-*` — 두 도구는 이 폴더를 같이 쓴다). 그래서 `/l-init`이 접두어 없이
그대로 불리고, git으로 팀원과 공유된다. `AGENTS.md`(공통 규칙)를 쓰고 `CLAUDE.md`는 `@AGENTS.md`로 불러온다.

| 도구 | 스킬 | 규칙 | 에이전트 hook | MCP (`--mcp`) |
|---|---|---|---|---|
| Claude Code | `.claude/skills` | `CLAUDE.md` → `@AGENTS.md` | `.claude/settings.json` | `.mcp.json` |
| Codex | `.agents/skills` (`$l-…`) | `AGENTS.md` | `.codex/hooks.json` | `.codex/config.toml` |
| Antigravity CLI (`agy`) | `.agents/skills` | `AGENTS.md` | `.agents/hooks.json` (압축 hook이 없어 H-8 제외) | `.agents/plugins/lanternspec/` |

Codex만 쓰면 스킬 본문의 호출이 `$l-build`로, Antigravity와 함께 쓰면 공용 폴더라 `/l-build`로 쓰이고
`AGENTS.md`가 Codex에게 `$`로 부르라고 알려 준다. (Gemini CLI는 Antigravity CLI로 바뀌어 더 지원하지 않는다.)

그다음 AI 도구 안에서:

```
/l-init          (Codex는 $l-init)
```

## 흐름

```mermaid
flowchart LR
  S["⚙️ /l-init"] --> I
  subgraph W["🛠 일하는 선로"]
    I["💡 /l-idea"] --> P["📋 /l-plan"] --> D["📐 /l-design"] --> T["✅ /l-task"] --> B["🔨 /l-build"]
  end
  P & D & B -.모르는 기술.-> L["🧭 /l-learn"]
  B -->|끝나면 합친다| C["📘 3. 현재 상태"]
  W & L --> R["📊 /l-report"]
```

| 명령 | 하는 일 | 남는 문서 |
|---|---|---|
| `/l-init` | 질문 7개(신규/기존 · 인원 · 화면 · 서버 · 지식 저장소 · 디자인 도구 · 프로젝트 종류)로 문서 구조와 개발 원칙을 정한다 | `lantern.yaml`, `docs/`, 프로젝트 정의서, MOC, 개발 원칙 |
| `/l-idea` | 대화 속 생각을 원문 + 정리본으로 바로 기록 | `1. 아이디어/IDEA-001 …` |
| `/l-plan` | 무엇을 · 왜 — 작업 폴더와 수락 기준 | `2. 작업/W-001 …/기획.md` |
| `/l-design` | 어떻게 — 바뀌는 구조 · 화면 · 데이터(DBML)만, 승인 게이트 | `설계.md`, `화면/`, ADR |
| `/l-task` | 순서 있는 할 일 목록 (크기 · 수락 기준 · 의존) | `할 일.md` |
| `/l-build` | 구현 → 테스트 → 할 일마다 커밋, **증거로** 보고, 끝나면 현재 상태에 반영 | 코드, `기록.md` |
| `/l-learn` | 모르는 기술을 지식 저장소와 비교 → 🟢 · 🟡 · 🔴, 부채 카드 · 학습 노트 초안 | `📒 부채/카드/D-001 …` |
| `/l-report` | 칸반 · 타임라인 · 도메인 · 추적 · 부채 · 문서-코드 일치 + 팀장 보고 3줄 | `4. 운영 기록/보고/현황.md` |
| `/l-template` | 양식 만들기 · 다듬기 · 옮기기 (내용은 잃지 않음) | `0. 템플릿/…` |
| `/l-check` | 양식 검사 (필수 칸 · 값 · 링크 · 버전 · ID · 길이) | — |
| `/l-sync` | 문서 ↔ 코드 어긋남을 찾아 맞추기 | — |
| `/l-map` | MOC(문서 지도) 갱신 | `개발문서 MOC.md` |
| `/l-adr` | 되돌리기 어려운 결정 기록 | `규칙 · 결정 기록/ADR-001 …` |

## 문서 구조 — 저장은 작업별, 보기는 단계별

```
docs/
├─ 개발문서 MOC.md        지도 + 단계별 보기 (lantern map이 표시 안쪽을 다시 씀)
├─ 0. 템플릿/              사람이 다듬어 가는 글 구조 · _meta/enums.yaml (선택지의 유일한 출처)
├─ 1. 아이디어/
├─ 2. 작업/W-012 …/        기획 · 설계 · 할 일 · 기록 — 일하는 동안 고치는 곳은 여기뿐
│   └─ 보관/
├─ 3. 현재 상태/           지금 시스템의 모습 — 작업이 끝날 때만 승인 후 갱신
├─ 4. 운영 기록/           보고 · (2인 이상) 회의록
├─ 5. 기존 문서/           (브라운필드) 원본 보관 — 고치지 않음
└─ 📒 부채/               카드 1장 = 부채 1개
```

어떤 문서가 켜지는지는 `lantern.yaml`의 답으로 **그때그때 계산**한다 (`lantern profile docs`).
`lantern.yaml`에는 사람이 답한 것만 적는다.

## 원칙

| # | 원칙 | 구현 |
|---|---|---|
| P1 | AI는 내용, 스크립트는 형식 | 번호 · 파일 · 폴더 · 검사 · 상태 변경은 모두 `lantern` CLI |
| P2 | 문서는 템플릿에서만 태어난다 | `lantern scaffold …` → AI는 `{{빈칸}}`만 채움. H-5 hook이 구조 변경을 그 자리에서 잡음 |
| P4 | 끝날 때 공통 마무리 | `lantern close <스킬>` = check → map → 실행 기록 |
| P5 | 쓰기 전에 보여 준다 | 설계 게이트 · 현재 상태 반영 승인 (`/l-idea`만 예외) |
| P6 | 남의 저장소는 읽기만 | 지식 연결기 `search · read · propose · write`, 쓰기는 승인 후 |
| P7 | 기존 시스템은 참고만 | 새로 구현 |

## 문서-코드 어긋남 — 막기보다 빨리 알아채기

| 장치 | 무엇 | 강도 |
|---|---|---|
| git `commit-msg` (H-1) | 커밋 메시지에 작업 ID `[W-012-T03]`, 할 일 섞임 | `git.hooks: warn \| block` |
| git `pre-commit` (H-2 · H-3) | 스키마 변경에 기록 · 바뀐 문서 양식 검사 | `warn \| block` |
| git `pre-commit` (구조) | 문서 저장 방식 규칙 (docs/.git · .gitignore · .ignore · 코드 커밋에 docs 섞임) | 항상 막음 |
| git `pre-push` (R6) | `docs-local` 브랜치 push | 항상 막음 |
| 에이전트 hook (Claude · Codex · Antigravity) | H-4 대화 시작 3줄 · H-5 문서 쓰면 바로 검사 · H-6 실행 기록 · H-7 `/l-sync` 권유 · H-8 압축 전 저장 · H-9 기술 질문 감지(`learn.detect`) · H-10 아이디어 감지(`idea.capture`) | — |
| CI (`lantern install --ci` · 끄기 `--no-ci`) | GitHub Actions에서 프로젝트 도구(언어별 uv · pnpm 등)를 준비한 뒤 `lantern check` + `lantern lint` + `lantern scan --tests` (린트 · 타입 검사 · 수락 기준 테스트가 깨지면 실패) | — |
| `lantern scan` | 주인 없는 커밋 · 오래된 문서(`checked_commit`) · 기록 없는 스키마 변경 · DBML↔마이그레이션 · 수락 기준 테스트 | `/l-sync` · `/l-report` |

```bash
lantern hooks install            # /l-init이 묻고 설치
lantern docs-mode local|shared   # 문서를 원격에 안 올리기: 같은 저장소의 orphan 브랜치 docs-local을 docs/에 펼침
lantern doctor                   # 구조가 lantern.yaml과 맞는지 한 번에 점검
```

## 배우는 선로 — 지식 저장소와 부채 장부

| 저장소 (`knowledge.type`) | 어떻게 | 쓰기 |
|---|---|---|
| `obsidian` · `folder` | Markdown 파일을 직접 읽음 (llm-wiki 포함) | 승인 후 노트 생성 (`propose_only`면 초안만) |
| `my_brain` | 볼트의 카드 색인 `.my-wiki/document_cards.jsonl`로 검색 (`4. Work` 제외) | 제안만 — `.my-wiki/workspace/lanternspec/`에 두고 승격은 볼트 규칙대로 |
| `notion` | Notion API (`path` = 부모 페이지 ID, 토큰은 `NOTION_TOKEN`) | 승인 후 부모 페이지 아래에 새 페이지 |

계약은 어디서나 `search · read · propose · write` 넷이고, CLI(`lantern knowledge …`)와 MCP 서버(`lantern mcp`, `lantern install --mcp`)가 같은 함수를 쓴다.
부채는 한 장부에 세 종류: 🧠 **이해**(또 물으면 셈, 해결 뒤 또 물으면 다시 엶) → `lantern debt promote`로 🛠 **역량**(연습 과제 · `debt practice` · ✍️ 연습 중) · 🧱 **기술**(`debt new --kind 기술`).

## 작업 방식 · 평가

- `lantern principles detect [--write]` · `show` — 프로젝트 종류 · 바깥 연결 · 규모(코드 줄 수 · 사람 수)로 **설계 원칙**(`principles.yaml`)과 언어별 **코드 컨벤션**(`conventions/<언어>.yaml`)을 표대로 골라 AGENTS.md(핵심)와 `개발 원칙.md`(자세히)에 넣는다. 기존 프로젝트는 이미 쓰는 린트 · 포맷 설정을 기록만 하고, 코드가 자라 규모 경계를 넘으면 `lantern doctor`가 원칙을 올릴지 묻는다
- `lantern harness suggest [--apply]` — 코드 크기 · 진행 중 작업 · `[P]` 할 일 · 테스트 유무 · 실행 기록으로 **하네스(작은 반복) · 루프(`build.loop: on`, `loop_limit`) · 그래프(worktree · 병렬 에이전트)** 중 하나를 추천
- `lantern eval` · `/l-report eval` — 실행 기록으로 스킬 · 모델 · 구성(설정값)별 비용(시간 · 도구 호출)과 결과(마무리 때 양식 오류)를 비교
- `lantern task add --parallel` (`[P]`) · `lantern task next --all` — 동시에 할 수 있는 할 일을 병렬 에이전트로
- `lantern task estimate W-012 [--apply]` — 크기별 실제 시간 중간값으로 예정일 **제안**
- 디자인 도구: Claude Design · Figma · Canva (각 도구의 MCP) — 시안은 늘 파일로 `lantern screen import W-012 <파일 · zip>`, 구현 캡처는 `lantern screen compare <캡처.png> <시안.png>`로 다른 곳을 먼저 짚고 사람이 확인

## CLI 한눈에

```text
설치     install [--tools] [--mcp] [--ci] · upgrade · build-adapters · doctor · harness suggest
프로필   profile show|docs|write|set · enums list|rename
문서     scaffold init [--plan] | work | doc | idea | adr | meeting | custom · new-id · map · meta get|set
검사     check [--changed] [--epic W-012] · check-dbml · dbml render|from-sql|diff
일       task next [--all]|start|done|ac|list|estimate · task add [--parallel] · pack · screen import|compare · work branch|start|list|finish|archive|stage · design approve · unit-log add · idea find|status
배움     knowledge search|read|propose|write|areas · debt find|new|ask|resolve|promote|practice|known|status|list · mcp
보고     report [--views] [--summary] · status · scan [--tests] · sync adopt · eval
양식     template list|lint|level|bump|outdated|diff|usage|new|migrate · legacy adopt|todos
git      hooks install|uninstall|status · docs-mode local|shared
마무리   close <스킬>
```

## 개발

```bash
uv sync                          # 의존성 + 개발 도구 설치 (.venv)
uv run pytest                    # 그 밖의 확인 명령은 AGENTS.md 2장
```

- 스킬 원본: `src/lanternspec/resources/skills/l-*/SKILL.md` (Agent Skills 표준 한 벌). 본문의
  `<!-- lantern:if key=value -->` 블록과 `<<plan.max_questions>>` 같은 값은 설치할 때 `lantern.yaml`로 채워진다.
  Codex용은 `/l-build` → `$l-build`로 바뀐다.

### 코드 구조

폴더는 "무엇이 바뀌면 여기를 고치나"로 나눴다. 한 가지 이유로 바뀌는 코드는 한 곳에 모이고,
다른 이유로 바뀌는 코드는 섞이지 않게 했다.

```text
src/lanternspec/
  core/       문서 형식의 바탕: project · profile · frontmatter · enums · state · templating · new_id · links · taskfile · meta
              (다른 그룹을 import하지 않는 맨 아래 층)
  work/       일하는 선로: scaffold · ideas · stages · tasks · branches · pack · epic_rules · dbml · screen
  learn/      배우는 선로: debt · knowledge/ (obsidian · folder · my_brain · notion · drafts · mcp_server)
  report/     읽어서 보여 주기: views · status · scan · doc_map · evaluate · harness
  check/      검사 · 양식 관리: check_docs · githooks · doctor · templates · legacy
  tools/      AI 도구 연결
                base.py         도구 어댑터 계약 (스킬 모양 · 설정 파일 · hook 입출력)
                claude.py · codex.py · antigravity.py   도구마다 한 파일 — 그 도구의 형식이 바뀌면 이 파일만
                skills.py       스킬 원본 → 렌더링 (도구와 무관)
                rules.py        AGENTS.md 블록
                agent_hooks.py  H-4~H-10이 *하는 일* (도구 형식을 모름)
                install.py · docs_mode.py · runlog.py · close.py
  cli/        명령: 그룹마다 한 파일(tools · core · work · learn · report · check) + common.py, __init__.py는 조립만
  resources/  코드가 아닌 원본 데이터: templates/ · skills/ · agents/ (설치할 때 프로젝트로 복사 · 변환)
```

새 AI 도구를 붙일 때는 `tools/base.py`의 `Tool`을 구현한 파일 하나와 `tools/__init__.py`의 `REGISTRY` 한 줄을 추가한다.
도구 하나가 형식을 바꾸거나 사라지면(예: Gemini CLI → Antigravity CLI) 그 도구 파일과 등록 한 줄만 바뀐다.
- 상태 · 유형의 이름과 아이콘: `enums.yaml` 한 곳 (기본값은 `src/lanternspec/resources/templates/_meta/enums.yaml`,
  프로젝트에서는 `docs/0. 템플릿/_meta/enums.yaml`). 코드는 이름 대신 role(`debt_status.resolved`)로 값을 찾고,
  스킬은 `<<debt_status.resolved.label>>`, 템플릿은 `${work_status.plan}`처럼 쓴다. 아이콘만 바꾸면 `lantern upgrade`,
  이름을 바꾸면 `lantern enums rename debt_status 되물음 "다시 물음"` — 이미 쓴 문서의 값과 스킬까지 함께 바뀐다.
- 기본 양식: `src/lanternspec/resources/templates/` — `/l-init`이 `docs/0. 템플릿/`으로 복사하고(출처 버전 기록),
  `lantern upgrade`는 사람이 다듬지 않은 양식만 새 버전으로 바꾼다.
- 설계 문서: `lantern_docs/00. Lantern SDD/09. 스킬별 구현 전략.md`
