# AGENTS.md — LanternSpec 개발 규칙

이 저장소(LanternSpec 자체)의 코드를 고치는 사람과 AI 에이전트가 따르는 규칙이다.
사용자 프로젝트에 설치되는 규칙은 따로 있다: `src/lanternspec/resources/agents/AGENTS.md` (헷갈리지 말 것).

## 0. 이 프로젝트

아래 원칙과 컨벤션은 이 프로젝트의 모양에 맞춰 고른 것이다. 모양이 바뀌면 고른 것도 다시 본다.

| 항목 | 값 |
|---|---|
| 종류 | CLI 도구 + 바깥 도구(Claude Code · Codex · Antigravity · 지식 저장소)에 붙는 어댑터 |
| 규모 | 소규모 — 1인, 모듈 68개, 코드 약 1만 줄 (테스트 약 2천 줄) |
| 언어 | Python 3.12 이상 |
| 특징 | 문서 로직은 오래 그대로 가지만, 바깥 도구의 형식은 자주 바뀐다 |

그래서 **기본은 단순하게**, 바깥 도구에 붙는 곳만 **바꿔 끼우기 쉽게** 만든다.

## 1. 설계 원칙

### 원칙이 부딪힐 때의 순서
1. **단순함이 기본이다.** 요청한 만큼만, 지금 필요한 만큼만 만든다.
2. **단일 책임 · 단일 출처 · 의존 방향은 어디서나 지킨다.** 단순함과 부딪히지 않고, 오히려 코드를 찾기 쉽게 만든다.
3. **개방-폐쇄 · 계약 지키기는 아래 "확장 지점"에서만 쓴다.** 다른 곳에 끼워 넣는 자리를 미리 만들지 않는다.
   새 확장 지점은 *두 번째 구현이 실제로 생길 때* 만든다.

### 단순함 (KISS · YAGNI)
- **왜:** 1인 소규모 프로젝트라 추상화의 비용(따라가기 어려움)이 이득보다 크기 쉽다.
- **어디에:** 모든 코드의 기본값.
- **지키는 법:**
  - 지금 쓰이지 않는 옵션 · 추상화 · 일반화는 넣지 않는다.
  - 한 번만 쓰이는 코드에 계층을 만들지 않는다. 200줄로 쓴 것이 50줄로 되면 다시 쓴다.

### 단일 책임 (SRP) — 바뀌는 이유가 하나
- **왜:** 고칠 일이 생겼을 때 고칠 곳이 한눈에 보여야 한다. 바깥 도구 하나의 형식이 바뀌면 그 도구 파일 하나만 고치면 되게 한다.
- **어디에:** 폴더 · 모듈 · 클래스 · 함수 모두.
- **점검 질문:** *"이 변경 이유 하나 때문에 고쳐야 하는 파일이 몇 개인가?"* 둘 이상이면 책임이 흩어졌다는 신호다.
- **폴더 = 바뀌는 이유:**

  | 폴더 | 책임 | 여기를 고치는 이유 |
  |---|---|---|
  | `core/` | 문서 형식의 바탕 (프로필 · frontmatter · 템플릿 채우기 · ID · enums …) | 문서와 프로필의 *형식*이 바뀔 때 |
  | `work/` | 일하는 선로 (아이디어 → 기획 → 설계 → 할 일 → 구현) | 일하는 순서나 단계의 규칙이 바뀔 때 |
  | `learn/` | 배우는 선로 (부채 장부 · 지식 연결기) | 부채를 세는 규칙, 지식 저장소와 주고받는 방식이 바뀔 때 |
  | `report/` | 읽어서 보여 주기 (보고 · 지금 상황 · 문서-코드 어긋남 · MOC) | 무엇을 어떻게 보여 줄지가 바뀔 때 |
  | `check/` | 검사와 양식 관리 (양식 검사 · git hook · doctor · 템플릿 버전) | "맞다 · 틀리다"의 기준이 바뀔 때 |
  | `tools/` | AI 도구 연결 (스킬 · 규칙 · 에이전트 hook 설치와 처리) | AI 도구의 형식이 바뀔 때 |
  | `cli/` | 명령 (그룹마다 한 파일) | 명령의 이름 · 옵션 · 출력이 바뀔 때 |
  | `resources/` | 코드가 아닌 원본 데이터 (템플릿 · 스킬 원본 · 규칙 원본) | 사용자에게 설치될 글이 바뀔 때 |

- **지키는 법:**
  - hook이 *하는 일*은 `tools/agent_hooks.py`, 도구별 *입출력 형식*은 그 도구 파일에 둔다.
  - 새 CLI 명령은 맞는 그룹의 `cli/<그룹>.py`의 `register()`에 넣는다. `cli/__init__.py`는 조립만 한다.
  - 모듈 docstring의 `하지 않는 일`을 지킨다. 거기 적힌 일이 필요하면 그 일을 맡은 파일을 고친다.

### 단일 출처 (DRY · SSOT) — 같은 사실은 한 곳에만
- **왜:** 같은 사실이 두 곳에 있으면 언젠가 둘이 달라지고, 하나를 바꿀 때 여러 파일을 찾아 고쳐야 한다.
- **어디에:** 이름 · 경로 · 아이콘 · 설정값처럼 여러 곳에서 쓰는 사실 모두.
- **출처 목록:**

  | 사실 | 단 하나의 출처 | 거기서 만들어지는 것 |
  |---|---|---|
  | 상태 · 종류의 이름 · 아이콘 | `enums.yaml` | 코드의 값 · 출력, 스킬 글, 템플릿 칸, 검사 |
  | 스킬 내용 | `resources/skills/l-*/SKILL.md` (한 벌) | 도구별 스킬 파일 (`lantern install`) |
  | 기본 문서 양식 | `resources/templates/` | 프로젝트의 `docs/0. 템플릿/` |
  | 설계 원칙 · 코드 컨벤션 기준 | `resources/principles/` (`principles.yaml` · `conventions/<언어>.yaml`) | 사용자 프로젝트 AGENTS.md의 개발 원칙 · `개발 원칙.md` |
  | 사람이 정한 프로젝트 설정 | `lantern.yaml` | 켜질 문서, 스킬에 들어가는 값 |
  | AI 도구가 쓰는 설정 폴더 | 각 `Tool.config_paths` | 문서-코드 어긋남 · 작업 방식 추천에서 "코드가 아닌 것" 판단 |

- **지키는 법:**
  - 상태 · 종류의 이름은 코드 · 스킬 · 템플릿에 직접 쓰지 않고 역할(role)로 찾는다.
    코드 `project.enums.value("debt_status", "resolved")` · 스킬 `<<debt_status.resolved.label>>` · 템플릿 `${work_status.plan}`
  - 만들어진 파일(스킬 · 보고 · MOC)은 손으로 고치지 않는다. 출처를 고치고 다시 만든다.
  - 이름 · 경로 · 아이콘을 문자열로 다시 쓰고 싶어지면, 먼저 그 출처를 찾아 거기서 가져온다.

### 의존 방향 (DIP) — 안쪽은 바깥을 모른다
- **왜:** 아래 층이 위를 모르면 아래 층을 따로 이해하고 테스트할 수 있다. 바깥 도구가 바뀌어도 안쪽은 그대로다.
- **어디에:** 그룹 사이의 import, 그리고 판단과 바깥 일(파일 · git · 네트워크 · 시각)의 경계.
- **지키는 법:**
  - 의존은 한 방향으로만 흐른다: `cli` → 각 그룹(`work` · `learn` · `report` · `check` · `tools`) → `core`.
    `core`는 위를 import하지 않는다. 그룹끼리 서로 필요하면 함수 안에서 import해 순환을 피한다.
  - 공유 코드는 계약(`Tool` · 지식 `Adapter`)만 알고, Claude · Notion 같은 구체적인 것은 모른다.
  - 판단은 순수 함수로, 바깥 일은 가장자리로 뺀다.
    예: `enums.rename_in_text`(글 → 글, 순수)와 `meta.rename_enum_value`(파일을 읽고 씀). 순수한 쪽은 Example · 테스트가 쉽다.

### 확장 지점 — 개방-폐쇄 (OCP) · 계약 지키기 (LSP · ISP)를 쓰는 곳
- **왜:** 이 프로젝트에서 구현이 여럿이거나 자주 바뀌는 곳들이다. 여기서만큼은 더할 때 기존 코드를 고치지 않게 한다.
- **어디엔 안 씀:** 아래 표에 없는 곳. 구현이 하나뿐인 곳에 인터페이스 · 레지스트리 · 분기 테이블을 만들지 않는다.
- **확장 지점:**

  | 지점 | 지금 구현 | 더하는 법 |
  |---|---|---|
  | AI 도구 | Claude Code · Codex · Antigravity | `tools/<도구>.py`(`Tool` 구현) + `tools/__init__.py`의 `REGISTRY` 한 줄 |
  | 지식 저장소 | obsidian · folder · notion | `learn/knowledge/<저장소>.py`(`Adapter` 구현) + `adapter_for`의 분기 + `core/profile.py`의 선택지 (아직 한 곳으로 모이지 않음) |
  | 상태 · 종류 값 | `enums.yaml`의 목록들 | `enums.yaml`에 한 줄 (코드 수정 없음) |
  | CLI 명령 | 6개 그룹 | 그룹 파일의 `register()`에 추가 |

- **계약을 지키는 법:**
  - 같은 계약의 구현은 **어디에 끼워도** 같은 약속을 지킨다.
    - 에이전트 hook은 어떤 입력에도 에이전트를 멈추게 하지 않는다 (오류는 삼키고 알린다 — `cli/tools.py`의 `cmd_hook`).
    - `respond`는 늘 그 도구가 받아들이는 형식으로 답한다 (예: Antigravity는 할 말이 없어도 `{}`).
    - 쓸 수 없는 저장소의 `write`는 조용히 넘어가지 않고 `KnowledgeError`로 거절한다.
  - 계약은 작게 둔다. 모든 구현이 쓰지 않는 기능은 기본 구현을 두어, 필요한 구현만 덮어쓰게 한다
    (예: `Tool.install_config` · `written_paths`의 기본값, `Adapter.areas`).
  - 확장 지점에서 `if 종류 == "…"` 분기를 여러 곳에 더하고 있다면 계약이 모자란다는 신호다 — 먼저 계약을 고친다.

## 2. 코드 컨벤션 (Python)

### 도구
모든 명령은 **uv로 실행한다** (`uv run …`). `.venv/bin/…`을 직접 부르거나 `pip`으로 설치하지 않는다.
`uv run`이 `pyproject.toml`의 의존성과 `[dependency-groups] dev`(개발 도구)를 알아서 맞춰 준다.
의존성을 더하거나 빼면 `uv add` · `uv remove`(개발 도구는 `--dev`)를 쓰고, 바뀐 `uv.lock`도 함께 커밋한다.

코드를 고친 뒤에는 늘 아래를 돌린다. 설정은 모두 `pyproject.toml`에 있다.

```bash
uv run ruff format src tests        # 코드 모양 맞추기 (black과 같은 역할)
uv run ruff check src tests         # 린트: pyflakes · pycodestyle · import 정렬 · bugbear · 최신 문법 · 타입 힌트 · docstring
uv run pyright                      # 타입 검사 (standard 모드)
uv run pytest                       # 테스트 + docstring Example
```

- 한 줄은 140자까지. 포맷터가 자르지 못하는 긴 문자열은 이어 붙는 조각(`"앞" "뒤"`)으로 나눈다.
- Python 3.12 이상을 지원한다 (`requires-python >= 3.12`, 개발 버전은 `.python-version`). 3.12까지의 문법은 자유롭게 쓴다.

### 배포
PyPI 업로드는 `.github/workflows/release.yml`이 한다 (Trusted Publishing — 토큰 없음). 사람이 하는 일은 태그까지다.
main에 push하거나 PR을 열 때마다 `.github/workflows/ci.yml`이 같은 확인 네 가지를 돈다 (배포는 하지 않는다).

```bash
# CHANGELOG.md · CHANGELOG.ko.md의 [Unreleased]를 [새 버전] - 날짜로 옮긴다
uv version 0.1.1                                   # 버전은 pyproject.toml 한 곳에만 있다
git commit -am "Release 0.1.1" && git tag -a v0.1.1 -m "LanternSpec 0.1.1"
git push origin main && git push origin v0.1.1      # 태그가 올라가면 확인 → 만들기 → 배포가 돈다
```

- 태그와 `pyproject.toml`의 버전이 다르거나 확인 네 가지 중 하나라도 실패하면 배포하지 않는다.
- 올리기 전에 실패했으면 고친 뒤 태그를 지우고(`git push --delete origin v0.1.1` · `git tag -d v0.1.1`) 다시 단다.
  이미 PyPI에 올라간 버전은 다시 올릴 수 없으니, 그 뒤의 수정은 버전을 올려 새 태그로 낸다.

### 타입 힌트
- 함수 · 메서드의 모든 인자와 반환값에 타입 힌트를 단다 (`ruff`의 `ANN`이 검사한다. 테스트 함수는 빼고).
- 3.12의 표기를 쓴다: `dict[str, int]` · `list[str]` · `X | None` · `collections.abc`의 `Callable` · `Iterator`.
  `typing.Dict` · `List` · `Optional` 같은 옛 표기는 쓰지 않는다 (`ruff`의 `UP`이 검사하고 `--fix`로 바꿔 준다).
- 모양이 정해지지 않은 데이터(YAML · JSON)에는 `Any`를 써도 된다.
- `pyright`는 0건을 유지한다. 피할 수 없는 경우만 줄 끝에 `# pyright: ignore[규칙]`과 이유를 적는다.

### docstring
기준 예시: `src/lanternspec/core/enums.py` — 새로 쓰거나 고칠 때 이 파일처럼 쓴다.

- **언어:** 설명은 한국어. 섹션 이름(`Args` · `Returns` · `Raises` · `Attributes` · `Example`)은 Google 스타일 그대로 영어.
- **모듈 (파일):** 첫 줄에 이 파일의 책임 한 줄. 한 줄로 부족하면 `책임:`과 `하지 않는 일:`을 나눠 적고,
  `하지 않는 일`에는 그 일을 맡은 파일을 함께 적는다.

  ```python
  """enums.yaml을 읽어 상태 · 종류 같은 선택지 목록을 제공한다.

  책임:
      - enums.yaml 읽기 (프로젝트 것, 없으면 패키지에 든 기본값)
      - 역할(role)로 이름 · 아이콘 찾기

  하지 않는 일:
      - 문서에 적힌 값 바꾸기 → core/meta.py (rename_enum_value)
  """
  ```

- **공개 함수 · 클래스:** Google 스타일로 요약 · (필요하면) 부연 · Args · Returns · Raises · Example을 모두 쓴다.
  클래스는 `Attributes`를 쓴다. Args에는 인자를 빠짐없이 적는다.

  ```python
  def rename_in_text(text: str, enum: str, old: str, new: str) -> str:
      r"""enums.yaml 글에서 값 하나의 이름을 바꾼다.

      그 목록 블록 안의 값 줄만 고치고 주석 · 순서 · 아이콘 · 역할은 그대로 둔다.

      Args:
          text: enums.yaml 전체 글.
          enum: 목록 이름.
          old: 지금 이름.
          new: 새 이름.

      Returns:
          이름을 바꾼 enums.yaml 글.

      Raises:
          LookupError: 목록이나 값이 없을 때.

      Example:
          >>> text = "debt_status:\n  values:\n    되물음: {icon: 🤔, role: asked_again}\n"
          >>> print(rename_in_text(text, "debt_status", "되물음", "다시 물음"), end="")
          debt_status:
            values:
              다시 물음: {icon: 🤔, role: asked_again}
      """
  ```

- **Example은 실제로 돌아가야 한다:** `pytest`가 `--doctest-modules`로 모든 Example을 실행한다. 틀린 예시는 테스트 실패다.
  코드를 바꿔 결과가 달라지면 Example도 같이 고친다. `\n` 같은 이스케이프가 든 docstring은 `r"""`로 연다.
- **예외:**

  | 대상 | 쓰는 법 |
  |---|---|
  | 내부 함수 (`_`로 시작) | 무엇을 하는지 **한 줄**. 이름만으로 뻔하면 생략해도 된다 |
  | CLI 명령 함수 (`cli/` 의 `cmd_*` · `register`) | **한 줄** — 인자가 argparse 결과 하나라 Args · Example이 반복일 뿐이다 |
  | 프로젝트 폴더 · git · 네트워크가 있어야 도는 Example | 줄 끝에 `# doctest: +SKIP`을 붙여 읽기용으로 둔다 |

- **검사:** ruff의 docstring 규칙(`D`, google)은 이 형식을 적용한 파일에만 켜져 있다.
  파일에 적용을 마치면 `pyproject.toml`의 `[tool.ruff.lint.per-file-ignores]` 목록에서 그 파일을 뺀다.

## 3. 작업 방식

AI와 함께 코드를 고칠 때 흔히 생기는 실수(카파시가 지적한 LLM 코딩의 문제들)를 막는 규칙이다.

### 코딩 전에 생각한다
- 가정과 모르는 것을 먼저 말한다. 해석이 여럿이면 하나를 몰래 고르지 말고 묻는다.
- 더 단순한 방법이 있으면 말한다. 요청이 이 문서의 원칙과 부딪히면 그 점을 먼저 짚는다.
- 기억에 기대지 않는다. 외부 도구 형식(Claude Code · Codex · Antigravity 설정 등)은 설치된 도구나 공식 문서에서 확인한다.

### 필요한 곳만 고친다
- 요청과 관련된 줄만 고치고, 주변 코드의 이름 · 주석 · 모양을 따른다.
- 관련 없는 정리 · 이름 바꾸기 · 리팩터링을 끼워 넣지 않는다. 보이면 따로 말한다.
- 내 변경 때문에 쓸모없어진 import · 함수는 지운다. 원래 있던 죽은 코드는 말만 하고 그대로 둔다.

### 목표로 검증한다
- 시작 전에 "무엇이 되면 끝인가"를 정한다. 가능하면 실패하는 테스트를 먼저 쓴다.
- 끝났다는 말 대신 결과를 보인다 — 2장의 도구 네 가지가 모두 통과해야 끝이다.
- 확인하지 못한 것(예: 로그인이 없어 실제로 돌려 보지 못한 도구)은 숨기지 않고 그렇다고 말한다.
