# 용어표 — LanternSpec 개발

LanternSpec이 이름을 쓰는 여러 곳(lantern.yaml 키 · enums.yaml 목록 · names.yaml 역할 · 스킬 · CLI 명령 · `Tool` · `Adapter` 계약)에서
**같은 낱말이 두 곳 이상에 나오는 것**을 모아 둔 표다. 새 이름을 만들기 전에 여기서 먼저 찾는다.

- 대부분은 한 개념을 여러 곳에서 쓰는 것이다 (`plan` = 기획 단계의 설정 · 문서 · 스킬).
- **⚠ 뜻이 다름**은 다른 개념이 낱말 하나를 나눠 쓰는 것이다. 읽거나 새로 쓸 때 어느 쪽인지 꼭 밝힌다.
- `tests/test_name_overlap.py`가 겹치는 이름이 이 표에 빠짐없이 있는지 확인한다. 겹침을 새로 만들면 테스트가 실패하니, 여기에 한 줄 더하거나 이름을 바꾼다.
  첫 칸의 `` `이름` ``만 읽는다 (단수 · 복수, `-` · `_`는 같은 것으로 본다).

## ⚠ 뜻이 다름

| 이름 | 뜻 | 쓰는 곳 |
|---|---|---|
| `language` · `languages` | `project.language` = 문서 · 스킬 · 메시지의 언어 (ko · en). `project.languages` = 코드의 프로그래밍 언어 목록 (python · typescript …) | lantern.yaml |
| `origin` | lantern.yaml `project.origin` = 새 프로젝트인가 (greenfield · brownfield). 보호 칸 `origin` = 부채 카드의 "어디서 나왔나" 칸 | lantern.yaml · names.yaml sections |
| `area` · `areas` | enums.yaml `area` = 부채의 주제 분류. `Adapter.areas()` = 지식 저장소 안의 영역(폴더) 목록 | enums.yaml · 지식 `Adapter` |
| `name` | lantern.yaml `project.name` = 프로젝트 이름. `Tool.name` · `Adapter.name` = 도구 · 저장소를 가리키는 키 (claude · obsidian) | lantern.yaml · `Tool` · `Adapter` |
| `hook` · `hooks` | `lantern hook` = AI 도구 · git이 부르는 내부 명령. `lantern hooks` = git hook 설치. lantern.yaml `git.hooks` = git hook의 세기 (warn · block). `Tool.hooks()` = AI 도구 설정에 넣는 hook 항목 | CLI · lantern.yaml · `Tool` |
| `debt_status` | enums.yaml `debt_status` = 부채 카드 하나의 상태 값 목록. 문서 `debt_status` = 부채 전체를 보여 주는 자동 생성 문서 "부채 현황" | enums.yaml · names.yaml docs |

## 한 개념, 여러 곳

| 이름 | 뜻 | 쓰는 곳 |
|---|---|---|
| `idea` · `ideas` | 아이디어 — 아직 작업이 아닌 생각 | lantern.yaml(`idea.capture`) · 문서 · 폴더 · CLI · 스킬 |
| `plan` | 기획 — 작업의 무엇 · 왜 · 수락 기준 | lantern.yaml(`plan.*`) · 문서 · 스킬 |
| `design` | 설계 — 기획을 어떻게 만들지, 승인 | lantern.yaml(`design.*`) · 문서 · CLI(승인 기록) · 스킬 |
| `task` · `tasks` | 할 일 — 작업 안의 한 줄 단위 일 | 문서 · CLI · 스킬 |
| `build` | 구현 단계. lantern.yaml `build.*`는 구현 때 쓰는 설정 (확인 명령 · 보고 주기 · 루프) | lantern.yaml · 스킬 |
| `work` · `works` | 작업 — 기능 · 변경 하나 = 폴더 하나 | 폴더 · CLI |
| `check` | 문서 양식 검사. lantern.yaml `check.*`는 그 기준 (최대 줄 수) | lantern.yaml · CLI · 스킬 |
| `report` · `reports` | 현황 보고 | lantern.yaml(`report.views`) · 문서 · 폴더 · CLI · 스킬 |
| `learn` | 배우는 선로 — 이해 부채를 지식 저장소와 비교 | lantern.yaml(`learn.*`) · 스킬 |
| `knowledge` | 지식 저장소 (Obsidian · 폴더 · Notion)와 그 연결기 | lantern.yaml · CLI |
| `debt` | 이해 부채와 그 장부 | 폴더 · CLI |
| `debt_card` · `debt_cards` | 부채 카드 — 부채 하나 = 문서 하나 | 문서 · 폴더 |
| `adr` | 결정 기록 (ADR) | 문서 · 스킬 |
| `map` | 문서 지도 (MOC) 갱신 | CLI · 스킬 |
| `sync` | 문서와 코드 맞추기 | CLI · 스킬 |
| `template` · `templates` | 양식 | 폴더 · CLI · 스킬 |
| `legacy` | 브라운필드의 기존 문서 | 폴더 · CLI |
| `principle` · `principles` | 개발 원칙 (설계 원칙 · 코드 컨벤션) | 문서(자동 생성) · CLI |
| `section` · `sections` | 보호 칸 — lantern이 제목으로 찾아 읽고 쓰는 `##` 칸 | lantern.yaml(`docs.sections`) · CLI |
| `unit_log` | 작업 단위 기록 — 사람이 `/l-plan`의 작업 단위 추천을 바꾼 이유 | 문서 · 보호 칸 · CLI(`unit-log`) |
| `data` | 데이터 문서와 그 폴더 (현재 상태 안) | 문서 · 폴더 |
| `screen` · `screens` | 화면 시안 — 문서 · 폴더 · 할 일 줄의 칸 · CLI | 문서 · 폴더 · 할 일 칸 · CLI |
| `meeting` · `meetings` | 회의록 | 문서 · 폴더 |
| `session` · `sessions` | 세션 기록 — 진행 중인 작업이 없을 때, 대화가 요약되기 직전의 상황을 남기는 문서 (하루 하나) | 문서 · 폴더 |
| `size` | 크기 — 할 일 줄의 `[크기:: M]`과 그 값 목록 | enums.yaml · 할 일 칸 |
