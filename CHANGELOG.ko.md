# 바뀐 점

[English](https://github.com/Jungjihyuk/LanternSpec/blob/main/CHANGELOG.md) · **한국어**

이 프로젝트의 바뀐 점을 버전마다 적는다.
형식은 [Keep a Changelog](https://keepachangelog.com/ko/1.1.0/), 버전은 [유의적 버전](https://semver.org/lang/ko/)을 따른다.

## [Unreleased]

업그레이드: `uv tool upgrade lanternspec` → 프로젝트마다 `lantern upgrade` (스킬 · 할 일 양식 · Obsidian 설정 갱신). 새 규칙 문서는 `lantern scaffold init`이 만들고, 예전 크기 이름(S · M · L)은 `lantern upgrade --apply`가 새 이름으로 바꾼다

### 추가
- **할 일 나누기 기준 문서** — `규칙/`에 크기 표와 "1d가 넘으면 나눈다", 모르는 것을 둘 곳(아이디어 · 설계에서 결정 · 조사 할 일 · 확인 필요), 조사 할 일의 규칙을 둔다. `/l-task` · `/l-build`가 이 문서를 읽고 따른다
- **조사 할 일** — `lantern task add --spike`가 제목 앞에 `[조사]`를 붙인다. 크기는 시간 상한이고, 결론은 ADR이나 기록에 남긴다
- **할 일 목록을 표처럼 (Obsidian)** — 할 일 이름은 왼쪽에, 크기 · 먼저 · 기준은 오른쪽 열에 맞춰 보인다. 파일은 할 일 한 줄 그대로다
- **타임라인: 쉰 시간 접기** — 할 일 없는 1시간 이상의 구간을 접고 `⋯ 5시간 ⋯`로 적는다. 칸 크기(5분 ~ 1시간)를 노트 너비에 맞추고, 날짜 목록으로 날짜를 오간다
- **타임라인: 걸린 시간** — 끝난 할 일 옆에 `T01 · 7분`, 끝난 작업 옆에 작업 시간 합계를 보여 준다

### 바뀜
- **할 일 크기 이름** — `S · M · L` → `15m · 1h · 반나절 · 1d` (영어판 `half`). 사람이 집중했을 때 걸릴 시간이고, 예전 이름도 그대로 읽는다
- **타임라인의 화살표** — "먼저 끝나야 하는 할 일"만 그리고, 끝난 작업에서는 할 일에 마우스를 올릴 때만 보인다. 막대 툴팁에 먼저 끝나야 하는 할 일을 적는다
- **타임라인 범례와 표시** — 범례는 차트에 있는 것만 맨 앞의 "한 칸 = 10분"과 함께, 시각 줄에 단위(`00시`), 작업 전체 기간은 꺾쇠 선(├──┤), 짧은 할 일의 이름은 막대 옆에
- **보고서의 빈 보기** — 보여 줄 게 없는 칸반 · 부채 현황 · 타임라인은 제목째 빼고, 맨 위 "보기:" 줄에도 보여 준 것만 적는다
- **`lantern enums rename`** — 크기 이름을 바꾸면 할 일 줄의 값도 함께 바꾼다

### 고침
- **타임라인에서 할 일이 겹쳐 보이던 문제** — AI가 몇 분 만에 끝낸 할 일들이 한 칸에 겹치고 화살표가 엉키던 문제를 고쳤다
- **칸반 칸에 문서 링크가 붙던 문제** — 할 일 칸에 `— [[설계#…]]` 같은 문서 링크가 그대로 들어가던 문제를 고쳤다

## [0.3.0] - 2026-11-10

**옮기는 법:** `lantern harness suggest`는 `lantern build-mode suggest`로 이름이 바뀌었다 (옛 이름은 당분간 안내와 함께 동작한다). 다른 작업이 진행 중일 때 `lantern work start`를 바로 부르던 곳은 `/l-parallel`을 거치거나 `--skip-check`를 붙인다. Codex는 프로젝트를 신뢰(trust)한 뒤에야 새 권한 설정을 읽고, 사용자 설정에 `sandbox_mode`가 있으면 그 설정이 이긴다 (`lantern doctor`가 알려 준다).

업그레이드: `uv tool upgrade lanternspec` → 프로젝트마다 `lantern upgrade` (`/l-parallel` · `/l-finish`를 설치하고, 규칙 문서 두 개 · 스킬 · 프로젝트 규칙 · Codex 권한 설정을 넣는다)

### 추가
- **`/l-parallel` — 동시 작업 시작 전 점검** — 작업들이 함께 정해야 할 것(공유 표 · 세션 · 토큰 · 권한 · 캐시)과 순서를 찾아 사람이 정하게 하고, ADR로 남긴 뒤 작업을 시작한다. 바로 시작할 작업이 하나뿐이면 worktree 없이 순서대로 진행한다
- **`/l-finish` — 동시 작업 마무리** — 기준 폴더에서 사람 확인을 모으고, 같은 일을 두 방식으로 만든 곳을 찾은 뒤, 작업을 하나씩 합친다. 현재 상태 반영 · 보관 · 보고는 한 번에 하고, 합친 브랜치를 지운다
- **`lantern work overlap`** — 작업들이 함께 쓰는 표 · 파일 · 결정 기록, 함께 바꾼 코드 파일, 새로 넣은 의존성을 시작하지 않고 보여 준다
- **기술 선택 기준 문서** — `규칙/`에 평가 기준 · 결정 트리 · 기술 비교표를 둔다. `/l-init`은 새 서비스 · 앱의 기술을 이 트리대로 추천하고, `/l-adr`은 기준 · 날짜 · 양식 버전을 함께 남긴다
- **저장소 파일 규칙 문서** — `.gitignore` · `docker-compose.yml`의 주석 구조, 프로젝트 수명에 따른 README · CHANGELOG 형식, 질문으로 고르는 라이선스, 폴더 구조를 담는다. 프로젝트 AGENTS.md가 이 파일들을 처음 만들 때 이 문서를 따르게 한다
- **`/l-init` 새 질문** — 얼마나 오래 쓸 프로젝트인지(`project.lifespan`), 저장소를 공개할지(공개면 LICENSE를 만든다), 서버를 만들면 개발 환경을 Docker로 맞출지를 묻는다
- **화면 확인** — `/l-build`가 화면 할 일을 AI 도구의 브라우저로 열어 캡처하고 인수 조건을 확인한다. 할 수 없으면 "사람 확인 대기"를 남기고 계속 진행하며, 합치기 전에 모아서 사람에게 묻는다. 설정은 `verify.browser`
- **문서 자동 커밋** — `/l-plan` · `/l-design` · `/l-task` · `/l-adr`이 끝날 때 그 작업의 문서만 커밋한다 (작업 폴더 · 설계가 따르는 결정 기록 · 연결된 아이디어 카드). 설정은 `docs.commit: auto | manual`, 명령은 `lantern close --commit`
- **`/l-design` 와이어프레임** — Claude Design 캔버스에 와이어프레임을 그려 `화면/`에 저장하고, 바꾸기 전 화면은 `화면/지금/`에 따로 둔다. 기존 UI가 있으면 `/l-init`이 `/design-sync`를 한 번 알려 준다
- **`lantern template show`** — 프로젝트에 아직 없는 기본 양식을 읽는다
- **한 작업만 다른 브랜치로** — `lantern work branch · start --into <브랜치>`는 그 작업만 다른 브랜치에서 시작해 거기로 합치고, `--here`는 작업 브랜치 없이 지금 브랜치에 커밋한다
- **Codex 권한 설정** — `lantern install` · `upgrade`가 `.codex/config.toml`에 `lantern` 권한 설정을 넣어 Codex가 커밋할 수 있게 하고, git hook과 config는 읽기만 하게 둔다. `lantern work start`는 도구마다 worktree를 여는 명령을 보여 준다

### 바뀜
- **`lantern harness` → `lantern build-mode`** — 반복 범위 · 할 일 나눠 맡기기 · 작업 동시 진행을 축마다 따로 추천한다. `--apply`는 반복 범위만 바꾼다
- **`/l-plan`은 필요한 화면 목록만** — 시안을 묻지 않는다. "시안과 같다" 인수 조건은 설계 때 더하고, 시안이 없다는 경고는 설계를 승인한 뒤에만 한다
- **`/l-design`이 지난 결정을 따른다** — 관련된 결정 기록을 읽고 다시 묻지 않으며, 설계의 `adr` 목록에 따른 결정도 넣는다
- **동시 작업은 점검 뒤에 시작** — 둘 이상의 작업이 함께 돌게 되면 `lantern work start`가 `--skip-check` 없이는 시작하지 않는다
- **worktree 안의 `/l-build`** — 자기 할 일과 기록만 커밋하고 멈춘다. 마무리는 기준 폴더의 `/l-finish`가 한다
- **보관 미루기** — 다른 worktree에서 진행 중인 작업이 링크하고 있으면 `lantern work archive`가 완료로만 표시하고 폴더는 그대로 둔다. `--now`는 바로 보관한다
- **`lantern work list` 표시** — `/l-finish` 대기, 이미 합쳐진 브랜치(지우는 명령과 함께), 끝난 작업의 남은 worktree, 보관 대기를 보여 준다
- **`/l-init` 질문 순서** — 무엇을 만드는지를 어디서 쓰는지보다 먼저 쉬운 선택지로 묻고, 후보가 둘 이상일 때만 고르게 한다

### 고침
- **worktree끼리 기록이 섞이던 문제** — 대화 요약 전에 저장하는 기록이 그 worktree의 작업에만 쓰이고, 날짜별 세션 문서도 worktree마다 따로 둔다
- **local 모드의 `docs` 링크가 새 파일로 잡히던 문제** — 저장소의 exclude 파일에 넣어 git이 무시하게 했다
- **만들어진 문서의 합치기 충돌** — 기준 쪽을 따른다. `/l-build`에 문서 · 데이터 · 코드 충돌을 푸는 순서를 넣었다
- **작업 마치기** — 기준 브랜치가 열린 폴더에서 합치고, 지울 수 없는 worktree는 통째로 남긴다. 충돌이 없는데 합치기가 실패하면 충돌이 아니라고 알려 준다

## [0.2.10] - 2026-11-04

업그레이드: `uv tool upgrade lanternspec` → 프로젝트마다 `lantern upgrade` (`/l-pr`을 설치하고 스킬의 새 규칙을 넣는다). `dev`나 PR을 쓰려면 `lantern profile set git.pr=deploy` 처럼 설정한 뒤 `lantern upgrade`를 한 번 더 한다

### 추가
- **`/l-pr` — PR 올리기** — 브랜치 방식에 맞는 방향을 찾아 커밋과 작업 문서로 제목 · 본문을 쓰고, 확인받은 뒤 push하고 PR을 만든다. 사람이 부를 때만 돌고, 합치지는 않는다
- **`/l-init` 브랜치 방식 질문** — 작업을 어떻게 합칠지 네 가지 중에 고른다: 단순하게 · 개발과 배포를 나누기 · 작업마다 PR · 지금 쓰는 방식 그대로. 추천은 `lantern work flow`가 브랜치와 원격을 보고 정한다
- **브랜치 설정** — `lantern.yaml`에 `git.branch`(이름 규칙) · `git.pr`(PR 방식) · `git.deploy`(배포 브랜치)가 생겼다. 기본값은 지금까지와 같다
- **브랜치 이름 규칙** — `feature/{id}-{slug}`처럼 규칙을 정하면 따르고, 맞지 않는 이름은 거절한다. 작업 ID 없는 이름은 `기획.md`의 `branch`로 작업과 잇는다. `lantern scaffold work --branch` · `lantern work branch --name`
- **구현 중 벗어난 일의 처리** — `/l-build`가 설계에 없는 일을 나눠서 다룬다: 큰 변경은 설계로, 작은 차이는 문서에 반영, 목적 밖의 일은 고치지 않고 아이디어 카드로, 먼저 해결해야 할 일은 멈추고 시작할 브랜치를 묻는다
- **사람이 바꾼 할 일 순서** — 할 일 순서가 마지막 커밋과 다르면 `lantern task next`가 경고하고, `/l-build`는 이유를 묻고 합의한 뒤에 이어 간다
- **PR 제목 · 커밋 검사** — `lantern check-pr`이 PR 제목과 코드 커밋의 작업 ID를 본다. `lantern install --ci`의 GitHub 검사에 들어가며, 기본은 경고만 하고 `git.hooks: block`이면 실패시킨다
- **PR · 커밋 양식** — `lantern install --pr-template` · `--commit-template`이 양식 파일을 만든다. 이미 있으면 그대로 둔다

### 바뀜
- **설치 · 업그레이드 출력** — 한 줄로 길게 이어지던 설정 목록을 파일마다 한 줄로 나누고, "설정 합침"을 무슨 일인지 알 수 있는 말로 바꿨다
- **새 작업 브랜치는 기준 브랜치에서** — `lantern work branch`가 현재 위치가 아니라 `git.base`에서 브랜치를 만들어, 다른 작업의 미완성 코드가 딸려 가지 않는다. 다른 브랜치에 있으면 멈추고, 그 위에 이어 만들려면 `--from <브랜치>`를 쓴다
- **작업 마치기** — `lantern work finish`가 기준 브랜치를 먼저 작업 브랜치에 합치고, 그 결과를 테스트한 뒤 병합한다. 작업 브랜치에 병합 커밋이 하나 더 생길 수 있다. 원격 기준 브랜치가 앞서 있으면 경고한다
- **AI 표시 빼기** — `/l-build` · `/l-pr`의 커밋 메시지와 PR에 AI가 작업했다는 표시를 넣지 않는다
- **아이디어 카드의 근거 읽기** — `/l-plan`이 카드에 링크된 근거 문서에서 카드에 적힌 항목만 읽는다

### 고침
- **다른 작업의 할 일을 먼저 끝낼 일로 지정** — `lantern task add --after`가 번호를 잘라 자기 작업의 할 일을 가리키던 것을 오류로 거절한다

## [0.2.9] - 2026-11-03

업그레이드: `uv tool upgrade lanternspec` → 프로젝트마다 `lantern upgrade` (Obsidian 플러그인을 쓰는 보관함에 Lantern Timeline 플러그인을 넣고 Metadata Menu 안내를 끈다. Obsidian을 닫고 실행한 뒤 다시 열면 켜진다) → `lantern report`로 보고서를 다시 만든다

### 추가
- **읽기 쉬운 타임라인 플러그인** — Obsidian 플러그인을 쓰는 프로젝트의 보고서 타임라인을 Lantern Timeline 플러그인으로 그린다. 왼쪽에 작업과 할 일 목록, 오른쪽에 날짜별 막대를 두고, 작업을 접고 펼칠 수 있으며, 할 일 이름을 누르면 `할 일.md`가 열린다. 상태와 오늘 위치 · 주말을 색과 점선으로 구분하고, 표시의 뜻은 범례에 적는다. 플러그인이 없는 프로젝트는 지금처럼 Mermaid로 그린다
- **타임라인에서 끌어서 일정 잡기** — 시작 전인 할 일은 막대를 끌어 옮기거나 양 끝을 끌어 기간을 바꿀 수 있다. 할 일 줄의 `[시작 예정::]` · `[마감 예정::]`에 저장되고, 실제 `[시작::]` · `[완료::]`는 바뀌지 않는다
- **타임라인의 선후 관계 화살표** — `[먼저::]` 관계를 화살표로 그리고, 시작 전인 할 일이 먼저 할 일보다 일찍 시작하면 빨갛게 표시한다
- **타임라인 즉시 반영** — 체크 표시 · `[시작::]` 값 · 예정일을 `할 일.md`에서 바꾸면 `lantern report` 없이 바로 보인다. 실제 날짜 · 제목 · 할 일 추가와 삭제는 `lantern report`를 다시 실행할 때 반영된다

### 바뀜
- **타임라인 제목** — 보고서의 `📅 타임라인 (WBS)`를 `📅 타임라인`으로 줄였다

### 고침
- **타임라인에 문서 링크가 섞이던 것** — 할 일 이름에 붙은 `[[…]]` 링크를 빼고 보여 주고, 작업을 번호순으로 놓는다
- **Metadata Menu 안내 문구** — LanternSpec에 필요 없는 DataviewJS를 켜라는 안내가 Obsidian을 열 때마다 뜨던 것을 끈다. DataviewJS는 켜지 않는다

## [0.2.8] - 2026-11-03

업그레이드: `uv tool upgrade lanternspec` → 프로젝트마다 `lantern upgrade` (`/l-ref` · `/l-domain` · `/l-idea` · `/l-plan` 스킬과 아이디어 · 역량 카드 양식을 새로 만들고, `enums.yaml`에 아이디어 상태 "막힘"을 더하며, CI를 쓰는 프로젝트는 CI 파일을 다시 만든다)

### 추가
- **원본 변환 `lantern ref convert`** — 도메인 지식 폴더의 PDF · DOCX · PPTX · HWP · HWPX는 절로 나눈 Markdown 변환본으로, XLSX · CSV는 시트 · 열 · 행 수와 앞 몇 줄만 담은 카드로 원본 옆에 만든다. 기본은 목록만 보여 주고 `--apply`일 때 쓴다. 품질(좋음 · 확인 필요 · 글자 없음)을 표시하고, 같은 파일은 한 번만 변환하며, 원본이 바뀌면 다시 변환하되 손으로 고친 변환본은 덮어쓰지 않는다. 한 파일이 실패해도 나머지는 계속한다. PDF는 `pdftotext`(poppler)가 필요하다
- **절 미리보기 `lantern ref preview`** — 문서를 절마다 주소 · 줄 수 · 첫 줄로 보여 준다. `/l-ref domain`이 원문 전체 대신 이것을 보고 설명을 제안해 토큰을 아낀다
- **막힌 아이디어** — 원하지만 기술 한계 · 실력 · 경험 때문에 지금은 못 하는 것을 아이디어 상태 🚧 막힘으로 남긴다. `lantern idea status IDEA-014 막힘 --reason "…" --revisit "…"`로 이유와 다시 볼 조건을 함께 적고, 개발문서 MOC가 막힌 아이디어를 따로 모아 보여 준다. 실력 때문에 막혔으면 `lantern debt promote IDEA-014`로 역량 카드를 만들어 서로 잇는다
- **CI의 린트 오류 처리 `build.ci_lint`** — `warn`이면 오류를 보여 주되 CI를 통과시키고, `block`이면 실패시킨다. 적지 않으면 기존 프로젝트는 `warn`, 새 프로젝트는 `block`이다. 테스트 실패는 설정과 상관없이 CI를 실패시킨다. 이제까지 린트 오류로 CI가 실패하던 기존 프로젝트도 통과하게 되니, 계속 막으려면 `build.ci_lint: block`을 적는다

### 바뀜
- **상태 표시에 색** — 터미널에서 `lantern doctor` · `lantern check` 등의 ✔는 초록, ℹ는 청록으로 표시하고, ⚠ 경고와 ✖ 문제는 줄 전체를 노랑 · 빨강으로 보여 준다. 파일 · 파이프로 보내거나 `NO_COLOR`를 켜면 지금처럼 색 없이 나온다. `lantern doctor` 맨 아래 요약도 "문제 0개 · 경고 3개"처럼 말로 쓴다
- **영역마다 검사** — `lantern lint`와 `lantern scan --tests`가 영역(`code.parts`)마다 적힌 명령을 그 폴더에서 실행한다. 영역에 명령이 있으면 `build.*`를 대신하므로, 평소 `lantern lint`도 모든 영역을 검사한다. 무거운 영역은 그 영역에 `ci: false`를 적어 CI에서 뺀다

### 고침
- **모노레포의 CI 실패** — `backend/pyproject.toml`처럼 설정 파일이 하위 폴더에 있으면 CI가 루트에서 `uv sync`를 돌려 실패하던 것을 고쳤다. 이제 영역(`code.parts`)마다 그 폴더에서 도구를 준비하고, 실행 도구도 그 폴더의 lock 파일로 판단한다. 설정 파일이 아직 없으면 준비 명령을 건너뛴다
- **도메인 지식에 "frontmatter가 없습니다" 경고** — `lantern check`가 양식이 없는 도메인 지식 문서를 양식 검사 대상으로 보던 것을 고쳤다
- **변환 안 된 원본이 보이지 않던 것** — `lantern doctor` · `lantern ref domain`이 변환을 기다리는 원본 수를 알려 준다

## [0.2.7] - 2026-11-02

업그레이드: `uv tool upgrade lanternspec` → 프로젝트마다 `lantern upgrade` (기본 양식 · `/l-template` 스킬 · Obsidian CSS 조각을 새로 만든다)

### 바뀜
- **양식 버전 안내를 알아보기 쉽게** — `lantern check`의 "양식이 바뀌었습니다" 안내가 LanternSpec 버전이 아니라 양식 자체의 버전임을 밝히고("이 문서를 만든 뒤 … 양식 버전 1.0.0 → 1.1.0 — LanternSpec 버전과 별개"), 그 문서에 반영하는 명령(`lantern template migrate`)을 함께 보여 준다
- **양식 안내를 읽기 쉽게** — 기본 양식 22개의 안내 상자를 다듬었다. 긴 안내는 첫 줄에 핵심을 두고 목록으로 나눴고, ✕ ○ ✚ 같은 기호와 설정 키 · 내부 이름은 말로 풀었으며, 뜻이 설명되지 않던 "🟦 원본 칸" 표시를 뺐다 (⚙️ lantern이 채우는 칸, 🔗 링크만 두는 칸만 남김). 기획 · 설계 · 할 일 · 기록의 "한눈에 보기" 빈칸에는 무엇을 쓸지 적었다. 문구만 바뀐 양식은 끝자리만 올라 `lantern check`가 기존 문서에 알리지 않는다
- **협업 규칙의 "작업 단위" 칸은 "작업 나누기"로** — `작업 나누기 기준` 문서 이름과 맞췄다 (양식 1.1.0)
- **lantern이 읽는 칸의 여러 줄 안내** — "지금 상황" · "참고한 도메인 지식"처럼 lantern이 읽고 쓰는 칸에서, `> [!guide]` 다음 줄로 이어지는 안내도 내용이 아닌 안내로 본다

### 고침
- **도메인 지식 폴더에도 색** — Obsidian 파일 목록에서 `📚 도메인 지식` 폴더만 색 상자 없이 보이던 것을 고쳤다. 폴더가 여덟 개가 되어, 목록 순서대로 빨강 · 주황 · 노랑 · 초록 · 청록 · 파랑 · 보라 · 분홍으로 한 칸씩 밀었다 (`📒 부채`는 그대로 빨강, `5. 기존 문서`가 분홍)

## [0.2.6] - 2026-11-01

업그레이드: `uv tool upgrade lanternspec` → 프로젝트마다 `lantern upgrade` (새 스킬 `/l-ref` · `/l-domain`, 기획 양식 1.1.0, AGENTS.md 규칙을 새로 맞춘다) → 용어집 · 도메인 지식 폴더가 필요하면 `lantern scaffold init`

### 추가
- **참고 자료 들이기 (`/l-ref` · `lantern ref`)** — 사내 규칙 · 용어집 · 도메인 지식을 프로젝트 안(상대 경로)이든 밖(`~/…` · 절대 경로)이든 그대로 두고 절 단위로 색인한다. `lantern ref index <rules|terms|domain> <경로>`가 새로 생긴 · 바뀐 · 사라진 절을 보여 주고, `lantern ref read "<문서>#<절>"`이 그 절만 읽는다 (긴 절은 나눠 읽을 부분을 안내). `lantern ref check`는 제목이 없거나 급을 건너뛴 문서처럼 나눠 읽기 어려운 구조를 알린다. 밖의 자료는 경로 · 제목 · 색인까지 모두 `.lantern/`에만 두어 git에 올라가지 않는다
- **사내 규칙을 AGENTS.md로 (`lantern ref tag` · `rules` · `exclude`)** — 절마다 적용 범위(전체 · 영역 폴더 · 언어)와 강도(반드시 · 되도록)를 승인받으면, 안의 규칙은 맞는 루트 · 영역 `AGENTS.md`에 원문 그대로 들어간다 (길이 예산을 넘으면 "되도록" 규칙은 제목과 읽는 명령만 남긴다). 밖의 규칙은 `AGENTS.md`에 내용 없는 한 줄만 두고 `lantern ref rules <영역>`이 보여 주며, 대화 시작과 요약 직후 hook이 "반드시" 규칙을 다시 건넨다. 이 프로젝트에 맞지 않는 절은 `lantern ref exclude`로 뺀다
- **용어집과 쓰지 말 표현 (`lantern ref terms` · `glossary` · `term`)** — 프로젝트 용어집(`3. 현재 상태/용어집.md`)과 승인한 사내 용어를 한 표로 보여 주고, 같은 용어가 둘 다에 있으면 사내 것을 따른다. 용어마다 "쓰지 말 표현"을 두면 `lantern check`가 문서에서 그 말을 찾아 "'포스팅' — '채용 공고'로 쓰세요"처럼 알린다. 대화에서 용어의 뜻을 물으면 hook이 용어집의 뜻을 함께 건넨다
- **용어 후보 모으기 (`references.terms_detect`)** — 문서에 쓰인 말의 뜻을 물으면 후보로 모아 두고, 스킬 마무리(`lantern close`)와 `lantern ref terms`에서 용어집에 넣을지 묻는다 (`lantern ref candidate`로 넣거나 `--drop`으로 뺀다). 기본은 `auto`, `ask` · `manual`로 바꿀 수 있다
- **도메인 지식 (`📚 도메인 지식/` · `lantern ref domain` · `describe`)** — 법령 · 정책 · 업무 규칙 문서를 이 폴더에 넣으면 따로 등록하지 않아도 색인된다. 절마다 무엇 · 언제 읽나 · 핵심 용어 · 원문 필수 여부를 적어 두면, `lantern ref domain`이 AI가 고를 색인을 보여 주고 `도메인 지식 MOC.md`가 Obsidian에서 같은 색인을 보여 준다. 원문 필수 절은 읽을 때 📌 표시가 붙고, 요약 직후 hook이 오늘 읽은 도메인 지식을 다시 알려 준다
- **작업에 도메인 지식 연결 (`lantern ref attach`)** — `/l-plan`이 필요한 절을 골라 기획의 새 칸 "참고한 도메인 지식"에 링크로 남기고, `/l-task`가 절마다 쓰는 할 일을 정하며, `/l-design`은 연결된 절만 읽고 빠진 것이 있는지 한 번 묻는다. `/l-build`는 할 일을 시작할 때 그 할 일에 연결된 절만 읽는다 (`lantern ref domain --work W-012 --task T03`). 밖의 자료는 기획 문서에 적지 않고 `.lantern/`에만 둔다
- **`/l-domain` 스킬** — 작업 선로 밖의 질문이나 설계 판단이 도메인 규칙에 달렸을 때, AI가 스스로 색인에서 맞는 절을 찾아 그 절만 원문으로 읽는다

### 바뀜
- **기획 양식 1.1.0** — "참고한 도메인 지식" 칸이 더해졌다. 그 전 양식으로 만든 기획은 `lantern check`가 이 칸을 묻지 않고, 처음 연결할 때 칸이 끝에 생긴다
- **가져오기만 하는 CLAUDE.md를 지움** — `@AGENTS.md` 한 줄뿐인 `CLAUDE.md` · `.claude/CLAUDE.md`를 `lantern install` · `lantern upgrade`가 지운다. 그 파일이 있으면 Claude Code가 영역별 `AGENTS.md`를 읽지 않기 때문이다. 직접 쓴 내용이 있거나 `CLAUDE.local.md`가 있으면 그대로 둔다

## [0.2.5] - 2026-10-31

### 고침
- **영역 안의 폴더를 다시 묻지 않음** — 여러 앱을 묶는 폴더(예: `pnpm-workspace.yaml`이 있는 `frontend`)를 영역으로 정하면, 그 안의 앱(`frontend/apps/web`)을 더는 정하지 않은 후보로 묻지 않고 `lantern parts`에 "영역 frontend에 포함"으로 보여 준다. 그 영역의 근거도 "패키지 설정 파일이 더는 없음" 대신 자기 `package.json`으로 나온다
- **지운 하위 `AGENTS.md`를 더는 경고하지 않음** — 지웠지만 아직 커밋하지 않은 하위 `AGENTS.md`가 `lantern doctor` · `lantern upgrade`에서 "자동으로 전달되지 않습니다" 경고와 길이 예산 점검에 계속 나오던 문제를 고쳤다

## [0.2.4] - 2026-10-30

업그레이드: `uv tool upgrade lanternspec` → 프로젝트마다 `lantern upgrade` (`/l-init` 스킬 문구를 새로 맞춘다)

### 바뀜
- **`lantern parts` 설명을 쉬운 말로** — 영역을 "저장소 안의 하위 프로젝트(언어와 검사 명령이 따로인 폴더)"로 풀어, 실행하면 맨 위에 영역이 무엇이고 정하면 어떻게 되는지 먼저 보여 준다. "자기 도구" · "매니페스트" 대신 "패키지 설정 파일(pyproject.toml · package.json 등)"이라고 쓰고, 후보가 없을 때는 "나눌 필요 없이 루트 AGENTS.md 하나로 프로젝트 전체를 다룹니다"라고 알린다 (`--help` · `lantern doctor` · `lantern.yaml` 주석 · `/l-init`도 같은 말로)

## [0.2.3] - 2026-10-30

업그레이드: `uv tool upgrade lanternspec` → 프로젝트마다 `lantern upgrade` (스킬 · 에이전트 hook · AGENTS.md 규칙을 새로 맞춘다)

### 추가
- **폴더마다 자기 규칙 두기 (`lantern parts`)** — 루트 아래에 자기 매니페스트를 가진 폴더(예: `backend` · `frontend/apps/web`)를 후보로 찾아 보여 주고, `lantern parts add <폴더>` · `lantern parts ignore <폴더>`로 정한다 (`/l-init`은 후보가 둘 이상일 때 묻고, 정하지 않은 후보는 `lantern doctor`가 알린다). 영역이 둘 이상이면 폴더마다 그 언어의 컨벤션과 확인 명령이 든 `AGENTS.md` 블록이 생기고, 루트 `AGENTS.md`에는 컨벤션 대신 영역 지도가 들어간다 (하나 이하면 전과 같다)
- **하위 `AGENTS.md`를 직접 읽지 않는 도구에 영역 규칙 전달** — Claude Code는 하위 `AGENTS.md`를 직접 읽고, 그렇지 않은 Codex(`PreToolUse` hook으로 그 영역을 처음 고치기 직전)와 Antigravity(처음 고친 뒤 다음 호출, 그리고 압축 hook이 없어 매 호출마다 지금 어디까지 왔는지 짧은 안내)에는 hook이 그 영역의 `AGENTS.md`를 대화당 한 번 건넨다. 영역 폴더 바로 아래가 아닌 다른 하위 `AGENTS.md`가 있으면 어느 도구가 읽지 못하는지 `lantern doctor`와 `lantern upgrade`가 알려 준다
- **`AGENTS.md` 길이 예산 점검** — 설치한 AI 도구가 끝까지 읽는 한도(Claude Code 200줄 권장 · Codex 32KiB · Antigravity 파일당 24,000바이트, Codex hook이 더하는 문맥 한도는 8,000토큰으로 높임)에 여유를 둔 예산과 루트 · 하위 `AGENTS.md`를 비교해 `lantern doctor`가 보여 주고, 넘으면 LanternSpec 블록과 직접 쓴 글이 각각 얼마인지 알려 준다 (`lantern upgrade`도 멈추지 않고 같이 알린다)

## [0.2.2] - 2026-10-30

업그레이드: `uv tool upgrade lanternspec` → 프로젝트마다 `lantern upgrade` (새 스킬 `/l-resume`을 설치하고, `.lantern/.gitignore`에 대화 기록 폴더를 더한다)

### 추가
- **지난 대화 이어 가기 (`/l-resume` · `lantern resume`)** — Claude Code · Codex · Antigravity 중 어느 도구에서 하던 대화든, 중간에 끊겼든 정상으로 끝났든, 멈춘 곳(마지막 요청 · AI의 마지막 말 또는 하던 일 · 고친 파일 · 커밋 안 된 변경 · 진행 중인 작업)을 보여 주고 이어 간다. 대화 기록 파일의 위치는 hook이 대화마다 적어 두므로 찾을 필요가 없다. 끊긴 대화는 "⚠ 끊김"으로 표시되고, 기본은 끝부분만 보여 주며 `--more`로 더 앞을 읽는다. 이 버전으로 업그레이드한 뒤에 연 대화부터 기록된다

### 고침
- `.lantern/.gitignore`가 처음 만들어질 때만 쓰여, 새 버전이 더한 개인 기록 폴더가 git에 잡힐 수 있던 문제 — 이제 빠진 항목을 더한다

## [0.2.1] - 2026-10-30

### 바뀜
- **문서를 옮긴 뒤의 안내** — `lantern upgrade --apply`가 옮기기 커밋을 한 뒤 이어지는 갱신(템플릿 · MOC · 설정)으로 바뀐 문서가 있으면, 몇 개인지 알리고 확인 후 커밋하라고 안내한다
- **템플릿이 조금 바뀌었을 때의 안내** — `lantern check`와 `lantern template outdated`가 "새 칸이 생겼다"고 단정하지 않고, 무엇이 바뀌었는지 양식의 '변경 기록' 칸을 보라고 안내한다
- **Antigravity 1.4.10** — hook 형식이 그대로인 것을 확인해, `lantern doctor`가 1.4.10을 확인된 버전으로 본다

## [0.2.0] - 2026-10-30

**옮기는 법:** 현재 상태 폴더의 구조가 바뀌었다 (`규칙 · 결정 기록/` → `규칙/` · `결정 기록/`, `배포` · `서버 배포 · 운영` → `배포 · 운영/`, `작업 단위 기록` → `작업 나누기 기준`). `uv tool upgrade lanternspec` 뒤 프로젝트마다 `lantern upgrade`로 옮길 문서를 확인하고 `lantern upgrade --apply`. 문서에 커밋하지 않은 변경이 있으면 먼저 커밋한다 (local 모드에서 문서를 한 번도 커밋하지 않았다면 `docs/` 안에서 먼저 커밋).

업그레이드: `uv tool upgrade lanternspec` → 프로젝트마다 `lantern upgrade` (스킬 · 규칙 · 템플릿 · Obsidian 스니펫을 새로 맞춘다)

### 추가
- **문서 위치 맞추기** — `lantern upgrade`가 문서를 frontmatter id로 알아보고, 지금 구조와 다른 곳에 있으면 옮길 목록을 보여 주고 멈춘다. `lantern upgrade --apply`는 git으로 옮기고(이력 유지), 깨질 링크와 옛 템플릿 이름을 고치고, 커밋 하나로 남긴다. 어느 옛 버전의 구조에서도 동작한다
- **AI 도구 점검** — `lantern doctor`가 설치한 AI 도구마다 버전(확인된 버전보다 낮거나 높은지), hook이 실제로 실행되는지, hook 입력에 빠진 값이 있는지 알려 준다
- **Obsidian 폴더 · 파일 아이콘** — 플러그인 없이 CSS 스니펫만으로 하위 폴더와 파일 앞에 아이콘이 붙고, 단계 상자가 폴더 전체를 감싼다

### 바뀜
- **현재 상태 폴더 정리** — `규칙/`(협업 규칙 · 개발 원칙 · 작업 나누기 기준), `결정 기록/`(ADR), `배포 · 운영/`(배포 · 서버 배포 · 운영)으로 나뉜다
- **작업 단위 기록 → 작업 나누기 기준** — 이름을 바꾸고 `규칙/`으로 옮겼다
- **작업 단위 선택지** — `/l-plan`이 "작업 하나 = 목적 하나"를 기준으로 새 작업 · 기존 작업에 넣기 · 나눠 담기 중에서 추천한다. 나눠 담기는 조각마다 어디로 갈지 이유와 함께 보여 준다. 할 일 10개 기준은 `/l-task` · `할 일` 양식에서도 없앴다
- **CLAUDE.md를 만들지 않음** — Claude Code 2.1.277+가 AGENTS.md를 직접 읽는다. 이미 있는 CLAUDE.md는 그대로 두고 `@AGENTS.md`만 넣는다(`.claude/CLAUDE.md`에는 `@../AGENTS.md`). CLAUDE.md 때문에 하위 AGENTS.md가 읽히지 않거나 `CLAUDE.local.md`가 있으면 `lantern doctor`가 알린다
- **보고서 요약 칸 이름** — "팀장 보고 3줄" → "3줄 요약"

### 고침
- local 모드에서 `lantern legacy adopt`로 옮긴 문서의 git 이력이 끊기던 문제

## [0.1.2] - 2026-10-29

업그레이드: `uv tool upgrade lanternspec` → 프로젝트마다 `lantern upgrade` (스킬 · 규칙 · AGENTS.md 블록을 새로 맞춘다)

### 추가
- **영어 지원** — `lantern install --language en`으로 스킬 · 템플릿 · 규칙 · 선택지 이름 · 폴더 이름, 명령 출력과 만들어지는 문서(MOC · 보고 · 부채 현황 · 개발 원칙 등)가 모두 영어로 나온다. 언어는 처음 설치할 때 정하고, `lantern.yaml`에 적힌 뒤에는 바뀌지 않는다
- **코드 주석 언어** — `lantern.yaml`의 `project.comment_language`(ko | en)로 문서와 코드 주석의 언어를 따로 정한다. 비우면 문서 언어를 따른다. `/l-init`이 묻고, AGENTS.md의 개발 원칙과 `개발 원칙.md`가 이 값을 따른다
- **보호 칸** — lantern이 읽고 써 넣는 칸(예: 기록의 "지금 상황")의 제목을 바꾸거나 지워도 다시 넣지 않는다. 그 기능만 건너뛰고 `lantern check`가 "일부러 바꾸셨나요?"라고 묻는다. 답은 새 명령 `lantern sections list|rename|off|on`으로 남기고, 목록은 `0. 템플릿/_meta/보호 칸.md`에 있다

### 바뀜
- **설치 안내** — lantern 명령이 없을 때 `/l-init`과 `lantern doctor`가 README와 같은 `uv tool install lanternspec`을 안내한다
- **문서를 원격에 안 올리는 설정** — `/l-init`이 `lantern docs-mode local`을 실행하기 전에, main에 설정 파일 3개를 커밋한다고 한 줄로 먼저 알린다
- **출력 문구** — 명령 출력 · 스킬 · 규칙에 남아 있던 기획 문서 번호를 지우고, 하는 일을 말로 적었다
- **질문 · 아이디어 알아채기** — 대화 중 기술 질문과 아이디어를 영어 표현으로도 알아본다("what is X", "how does X work", "I'd like to" 등)

### 고침
- Rust · Swift 컨벤션의 패키지 안내 글이 쉼표에서 잘리던 문제

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

[Unreleased]: https://github.com/Jungjihyuk/LanternSpec/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/Jungjihyuk/LanternSpec/compare/v0.2.10...v0.3.0
[0.2.10]: https://github.com/Jungjihyuk/LanternSpec/compare/v0.2.9...v0.2.10
[0.2.9]: https://github.com/Jungjihyuk/LanternSpec/compare/v0.2.8...v0.2.9
[0.2.8]: https://github.com/Jungjihyuk/LanternSpec/compare/v0.2.7...v0.2.8
[0.2.7]: https://github.com/Jungjihyuk/LanternSpec/compare/v0.2.6...v0.2.7
[0.2.6]: https://github.com/Jungjihyuk/LanternSpec/compare/v0.2.5...v0.2.6
[0.2.5]: https://github.com/Jungjihyuk/LanternSpec/compare/v0.2.4...v0.2.5
[0.2.4]: https://github.com/Jungjihyuk/LanternSpec/compare/v0.2.3...v0.2.4
[0.2.3]: https://github.com/Jungjihyuk/LanternSpec/compare/v0.2.2...v0.2.3
[0.2.2]: https://github.com/Jungjihyuk/LanternSpec/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/Jungjihyuk/LanternSpec/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/Jungjihyuk/LanternSpec/compare/v0.1.2...v0.2.0
[0.1.2]: https://github.com/Jungjihyuk/LanternSpec/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/Jungjihyuk/LanternSpec/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/Jungjihyuk/LanternSpec/releases/tag/v0.1.0
