---
name: l-build
description: 할 일을 구현하고 증거로 보고 — 작업(W-NNN 전체 또는 W-NNN-T03 하나)의 할 일을 순서대로 구현 → 테스트 → 할 일마다 커밋([W-NNN-T03]) → 체크하고, <<file.record>>에 바뀐 파일 · 테스트 결과 · 수락 기준 · 캡처 · 스키마 변경을 증거로 남긴 뒤, 끝나면 현재 상태에 반영할 요약을 보여 주고 승인받아 합친다. Use to implement a planned work.
invocation: model
argument-hint: "W-NNN | W-NNN-T03 [--report-cycle work|criterion|task]"
---

# /l-build — 구현하고 증거로 보고

**목적:** 할 일을 구현하고, **"끝났어요"가 아니라 증거로** 보고한다.

입력: `$ARGUMENTS` — `W-012`(전체) 또는 `W-012-T03`(하나). `--report-cycle task`처럼 이번 작업만 보고 주기를 바꿀 수 있다.
지금 설정: 보고 주기 `<<build.report_cycle>>` · 현재 상태 반영 `<<build.merge_approval>>`<!-- lantern:if build.test --> · 테스트 `<<build.test>>`<!-- lantern:endif -->

## 0. 준비
1. `<<file.tasks>>`가 없으면 멈추고 `/l-task`를 먼저 하자고 한다. 설계 승인(`<<file.design>>`의 `approved`)이 비어 있으면<!-- lantern:if design.approval=off --> 게이트가 꺼져 있으니 진행한다.<!-- lantern:endif --><!-- lantern:if !design.approval=off --> 멈추고 `/l-design` 게이트를 먼저 거친다.<!-- lantern:endif -->
2. 작업 하나 = 브랜치 하나: `lantern work branch W-012` (동시 작업용 worktree 안이면 이미 그 브랜치다 — 건너뛴다). 새 브랜치는 기준 브랜치 `<<git.base>>`에서 만든다. 다른 브랜치에 있어서 멈추면 사람에게 묻는다: 기준 브랜치로 옮길지, 그 브랜치 위에 이어 만들지(`--from <브랜치>` — 그 브랜치의 코드도 함께 합쳐진다). 브랜치 이름 규칙(`<<git.branch>>`)에 채울 칸이 있어 멈추면 사람과 정해 `--name <이름>`을 붙인다. `⚠ origin/…`이 나오면 기준 브랜치를 먼저 받을지 묻는다.
   **이번 작업만 예외 (사람이 말했을 때만 쓴다. 스스로 붙이지 않는다):** 합칠 곳을 바꾸려면 `--into <브랜치>` (그 브랜치에서 시작해 거기로 합친다), 작업 브랜치 없이 지금 브랜치에 바로 커밋하려면 `--here`. 명령이 `⚠`를 내면 사람에게 그대로 보여 준다.
3. 작업 꾸러미를 만들고 **그것만** 읽는다 (작업 폴더 + 관련 현재 상태 부분만 모은 한 번 쓰고 버리는 요약):
   ```bash
   lantern pack W-012     # → .lantern/pack/W-012.md
   ```
4. `<<file.record>>`가 없으면 `lantern scaffold doc W-012 "<<doc.record>>"`
5. 설계의 `adr`에 적힌 결정 기록을 읽고 따른다. 다른 작업과 함께 쓰는 선택(인증 · 공통 테이블 · API 형식 등)인데 설계와 결정 기록에 없으면 스스로 정하지 말고 멈추고 묻는다. 정해지면 `/l-adr`로 남기고, 보고에 "다른 동시 작업 세션에도 ADR-NNN을 읽으라고 알려 주세요"를 적는다.

## 1. 할 일 하나씩 (작은 반복)
```bash
lantern task next W-012          # 순서대로 지금 시작할 수 있는 할 일 (막힌 것은 이유와 함께 건너뜀)
lantern task next W-012 --all    # 지금 시작할 수 있는 할 일 전부 — [P] 표시는 서로 동시에 해도 되는 할 일
lantern task start W-012-T03     # [<<attr.start>>:: 시각]을 정확히 찍는다
```
**할 일 나눠 맡기기:** `--all`에 `[P]` 할 일이 둘 이상이고 이 도구가 서브 에이전트를 지원하면, `[P]` 할 일을 **하나씩** 서브 에이전트에 맡길 수 있다. 각자 같은 규칙(시작 · 증거 · 할 일 하나 = 커밋 하나)을 지키게 하고, 같은 파일을 고치는 할 일은 함께 맡기지 않는다. 지원하지 않으면 차례로 한다.

**도메인 지식:** 그 할 일에 연결된 것이 있으면 시작하자마자 **그 절만** 읽는다 — `lantern ref domain --work W-012 --task T03`이 보여 주는 `lantern ref read …`를 실행한다.
📌 원문 필수 절은 그 규칙을 코드로 옮기기 직전에 다시 읽는다. 구현 중 새로 필요해진 지식은 `/l-domain`으로 찾아 읽고 `lantern ref attach`로 연결한다.

1. 구현한다. 설계에 없는 일이 생기면 고치기 전에 아래 "구현 중 벗어난 일"로 나눈다.
2. 테스트한다<!-- lantern:if build.lint --> · 린트 · 타입 검사도 돌린다 (`lantern lint`)<!-- lantern:endif -->. 실패하면 고치고 다시 — **최대 3번**. 3번째도 실패하면 멈추고 보고한다.
3. `<<file.record>>`에 증거를 남긴다:
   - `## 증거` 표에 한 줄: 할 일 · 커밋(커밋 후 채움) · 바뀐 파일 · 테스트 결과(명령과 통과 수) · 수락 기준
   - 화면이면 캡처를 `<<folder.screens>>/구현/`에 저장하고 경로를 적는다
   - 스키마를 바꿨으면 `## <<section.schema>>`에 한 줄 (날짜 · 변경 · 이유/ADR · 마이그레이션 파일) — **실제 DB에 마이그레이션을 실행해야 하면 멈추고 묻는다**
   - `## <<section.now>>`은 덮어쓴다 (진행 · 다음 · 막힌 것, 3~5줄)
4. 체크하고 커밋한다:
   ```bash
   lantern task done W-012-T03      # [<<attr.finish>>:: 시각] + 수락 기준 체크포인트 알림
   ```
   커밋 메시지 형식 (사용자의 커밋 규칙이 있으면 그것을 따르고, ID는 끝에 둔다):
```
<<commit.template>>
```
<!-- lantern:if docs.remote=shared -->
   코드 + `<<file.tasks>>` + `<<file.record>>`를 **한 커밋에**: `git add … && git commit -m "feat: <무엇> [W-012-T03]"` (사용자의 커밋 규칙을 따르고 ID는 끝에). 커밋 후 증거 표의 커밋 칸을 채워 다음 커밋에 함께 넣는다.
<!-- lantern:endif -->
<!-- lantern:if docs.remote=local -->
   코드 커밋 `git commit -m "feat: <무엇> [W-012-T03]"` → 그 번호로 문서 커밋 `git -C docs add -- "<<folder.works>>/W-012 …" && git -C docs commit -m "docs: W-012-T03 기록 (code $(git rev-parse --short HEAD))" -- "<<folder.works>>/W-012 …"` (이 작업 폴더만 — 동시 작업 중인 다른 작업의 문서를 섞지 않는다). 코드 커밋에 `docs/`를 넣지 않는다.
<!-- lantern:endif -->
   여러 할 일을 한 커밋에 섞지 않는다. 할 일이 크면 같은 ID로 여러 커밋도 된다. 커밋 메시지에 AI가 작업했다는 표시(`Co-Authored-By` · `Generated with …` 등)를 넣지 않는다.
5. **수락 기준 체크포인트:** `task done`이 `AC 체크포인트: AC-1`을 알리면 그 AC만 따로 확인한다(관련 테스트 · 동작 확인). 통과하면 `lantern task ac W-012 AC-1`.

<!-- lantern:if plan.ui_reference=required -->
6. **화면 시안 확인:** `[<<attr.screen>>:: …]` 할 일이 끝나면 구현 화면을 캡처(`<<folder.screens>>/구현/…png`)하고, 시안도 PNG면 먼저 자동 비교로 다른 곳을 짚는다: `lantern screen compare "<<folder.screens>>/구현/로그인.png" "<<folder.screens>>/로그인.png"` (참고용). 그다음 둘을 **나란히 보여 주고 사용자에게 묻는다**: "시안과 같나요?" → 같으면 해당 AC 체크, 다르면 다른 곳마다 `lantern task add W-012 "<다른 곳 맞추기>" --size S --ac AC-n --screen "<화면>"`.
<!-- lantern:endif -->

## 1½. 구현 중 벗어난 일
**이 작업의 목적 안인가?** 작업 이름이 말하는 목적으로 설명되면 안, 아니면 밖이다. 다른 열린 작업에 어울려 보여도 옮기지 않고 밖으로 다룬다.

| 상황 | 처리 |
|---|---|
| 목적 안, 설계에 없는 **큰 변경** | 멈추고 보고한다 (→ `/l-design`) |
| 목적 안, 설계와 **작은 차이** | 계속한다. `<<file.design>>`를 실제에 맞추거나 `<<file.record>>`에 차이를 적는다 |
| 목적 밖, 지금 고치지 않아도 **지금 할 일의 수락 기준을 충족할 수 있음** | 고치지 않고 카드로 남기고 계속한다. 한 줄로 고칠 수 있어도 같다 |
| 목적 밖, 고치지 않으면 **수락 기준을 충족할 수 없음** | 멈추고 "먼저 해결할 일"로 간다 |

**카드로 남기기:** 직접 하지 말고 **서브 에이전트 하나에 맡기고** 하던 일을 계속한다 (간단해 보여도 맡긴다). 이 도구에 서브 에이전트가 없을 때만 그 자리에서 직접 한다. 서브 에이전트는 이 대화를 모르니 발견한 내용 · `파일:줄` · 작업 ID를 빠짐없이 넘기고, 아래 순서를 그대로 전한다:
```bash
lantern idea find "<핵심 단어 두세 개>"     # 같은 카드가 있으면 그 카드의 ## <<section.raw>>에 날짜와 함께 덧붙이고 끝낸다
lantern scaffold idea "<짧은 제목>" --kind <유형> --raw "W-012 구현 중 발견 (<파일:줄>): <내용>" --auto
```
만들어진 파일의 한 줄 요약 · 왜 좋은가를 채우고, 모르면 `<<marker.unknown>>`로 적는다. 쓸 것이 없는 선택 칸은 지운다. 카드는 할 일 커밋에 섞지 않고 `docs: IDEA-NNN 기록`으로 따로 커밋하며(서브 에이전트는 커밋하지 않는다), 받은 IDEA ID를 마지막 보고에 함께 알린다.

**먼저 해결할 일:**
1. 멈춘 이유를 `## <<section.now>>`에 적고, 지금까지의 변경을 작업 브랜치에 커밋한다 (할 일은 끝난 것으로 체크하지 않는다).
2. 어디서 시작할지 사람에게 묻는다. 추천은 기준 브랜치 `<<git.base>>`로 옮기는 것이다. 끝나지 않은 코드는 기준 브랜치에 합치지 않는다. 운영 중인 서비스의 장애라면 배포 브랜치(<!-- lantern:if git.pr=deploy -->`<<git.deploy>>`<!-- lantern:endif --><!-- lantern:if !git.pr=deploy -->`<<git.base>>`<!-- lantern:endif -->)에서 시작하는 것도 함께 제안한다. 그 브랜치가 기준 브랜치와 다르면 고친 뒤 두 브랜치에 모두 반영한다.
3. 옮긴 브랜치에서 카드를 직접 만들고(위 명령, 서브 에이전트 없이), `/l-plan IDEA-NNN`부터 진행하라고 안내하고 **여기서 멈춘다.**
4. 그 일이 끝나 합쳐지면 `git checkout <이 작업의 브랜치>` · `git merge <합쳐진 브랜치>` 후 `## <<section.now>>`을 보고 이어 간다.

**사람이 순서를 바꾸면:** 대화에서 말했거나 `lantern task next`가 `⚠ … 순서가 마지막 커밋과 다릅니다`를 알리면 다음 할 일을 시작하지 않는다.
1. 왜 바꾸는지 묻는다. 먼저 끝나야 할 일과 부딪히면 무엇이 위험한지 알려 주되, 정하는 것은 사람이다.
2. 합의되면 `<<file.tasks>>`의 줄 순서와 `[<<attr.after>>:: …]`를 고치고, 이유를 `<<file.record>>`에 한 줄 남기고, `lantern check` · `lantern report`를 돌려 문서를 커밋한다. 그다음 `lantern task next`로 다음 할 일을 제안한다.
3. 합의되지 않으면 사람에게 확인하고 순서만 원래대로 되돌린다.

`[<<attr.after>>:: …]`에는 이 작업의 할 일만 적는다. 다른 작업을 기다려야 하면 "먼저 해결할 일"로 다룬다.

## 2. 언제 보고하나
- `work`: 작업이 다 끝나면 · `criterion`: 수락 기준 하나가 완성될 때마다 · `task`: 할 일 하나마다
- **값과 상관없이 바로 보고하고 멈춘다:** 테스트를 3번 고쳐도 실패 · `<<marker.unknown>>`를 만남 · 화면 시안 확인 · 실제 DB 마이그레이션 실행 · 설계에 없는 큰 변경 · 먼저 해결할 일 · 사람이 바꾼 순서
- 보고는 3줄: **한 일 · 멈춘 이유 · 골라야 할 것**

<!-- lantern:if knowledge -->
## 3. 새 기술 · 라이브러리 → /l-learn 후보
구현 중 새 기술이 들어오면 후보로 모은다 (노트 있는 기술 · 아는 기술은 빼고, 최대 <<learn.max_candidates>>개). **작업은 멈추지 않고** 마지막 보고 때 보여 준다. 작은 라이브러리 선택은 `<<file.record>>` 결정 칸에 한 줄, 되돌리기 어려운 선택은 `/l-adr`.
<!-- lantern:endif -->

<!-- lantern:if build.loop=on -->
## 3½. 큰 반복 (build.loop: on · 최대 <<build.loop_limit>>번)
모든 할 일이 끝나면 수락 기준 테스트를 한꺼번에 돌린다<!-- lantern:if build.test --> (`<<build.test>>`)<!-- lantern:endif -->.
- 모두 통과 → 4단계로.
- 실패한 수락 기준이 있으면 → 실패마다 고칠 할 일을 추가하고(`lantern task add W-012 "<AC-n 맞추기>" --size S --ac AC-n`) 1단계부터 다시 돈다. `<<file.record>>`에 "큰 반복 n번째: 실패한 AC · 원인 한 줄"을 남긴다.
- <<build.loop_limit>>번을 돌아도 통과하지 못하면 멈추고 보고한다 (한 일 · 남은 실패 · 골라야 할 것).
<!-- lantern:endif -->

## 4. 모두 끝나면 — 현재 상태에 반영
`lantern task next W-012`가 **"이 폴더는 동시 작업용 worktree"**라고 알리면 여기서 멈춘다. 여러 작업이 함께 쓰는 문서는 `/l-finish`가 기준 폴더에서 한 번에 맞춘다:
- 이 작업의 문서를 모두 커밋한다: `<<file.tasks>>`, `<<file.record>>`, 대화 압축 때 자동으로 저장된 `<<folder.sessions>>/<날짜>-W-012.md`. 현재 상태 문서 · 보관 · 보고는 건드리지 않는다.
- `git status`에 남은 파일이 없는지 확인한다. 남은 파일이 있으면 `/l-finish`가 합친 뒤에도 이 worktree를 지우지 못한다.
- 마지막 보고: 증거 요약(할 일 · 커밋 · 테스트 · 수락 기준)과 "기준 폴더에서 `/l-finish W-012`를 실행해 주세요".

그렇지 않고 "모든 할 일 완료"를 알리면:
1. 설계의 변경분을 현재 상태에 합칠 **요약 한 장**을 보여 준다:
   ```
   📘 기능 목록  ✚ 카카오 로그인 (W-012)
   🏗 시스템 구조 ✎ 인증 흐름에 카카오 OAuth 추가
   🗄 데이터     ✚ users.kakao_id   (⚠ 데이터 구조 변경)
   🔌 API        —
   → [모두 반영] / [골라서 반영] / [고칠 곳]
   ```
   - `required`: 항상 묻는다. `auto`: 먼저 반영하고 요약을 보고한다 (잘못되면 git으로 되돌림).
   - **데이터 구조 · API 변경은 값과 상관없이 묻는다.**
2. 반영한다: 한 사실은 한 곳에 — 출처 작업을 링크한다.
   - 데이터: 설계의 DBML 변경분을 `<<folder.current>>/<<folder.data>>/schema.dbml`에 합친다 → `lantern check-dbml` → `lantern dbml render`
   - 반영한 문서의 확인 시점: `lantern meta set "<문서>" checked_commit=$(git rev-parse --short HEAD)` (관련 코드 경로가 늘었으면 `code`도)
<!-- lantern:if !git.pr=work -->
3. 작업 브랜치를 기준 브랜치에 합치고 정리한다 (기준 브랜치 받기 → 테스트 → 머지 → 정리). 충돌하면 아래 **충돌이 나면**을 따른다:
   ```bash
   lantern work finish W-012
   lantern work archive W-012      # 작업 폴더 → <<folder.archive>>/ (링크도 고쳐 준다)
   ```
   `finish`가 **폴더를 남겨 둔다**고 하면 worktree 안에서 실행한 것이다: `archive`부터 아래 4번과 문서 커밋까지 안내된 폴더로 옮겨서 하고, 끝으로 안내된 정리 명령을 실행한다. 그 명령이 세션에서 폴더를 지울 수 없다고 하면 다른 방법으로 지우지 말고(`git worktree remove`는 중간에 멈춰 폴더를 망가뜨린다) 터미널에서 실행할 명령을 사람에게 보여 준다.
<!-- lantern:endif -->
<!-- lantern:if git.pr=work -->
3. 기준 브랜치를 작업 브랜치에 받아 테스트하고, 합치는 것은 PR에 맡긴다. 충돌하면 아래 **충돌이 나면**을 따른다:
   ```bash
   lantern work finish W-012       # 기준 브랜치 받기 → 테스트 (머지는 하지 않는다)
   lantern work archive W-012      # 작업 폴더 → <<folder.archive>>/ (링크도 고쳐 준다)
   ```
   문서를 커밋한 뒤 사람에게 `/l-pr`을 실행하라고 안내한다.
<!-- lantern:endif -->
   **충돌이 나면:** 자동 생성 문서만 충돌하면 `finish`가 알아서 처리한다. 다른 파일이 함께 충돌해 멈추면 안내대로 작업 브랜치에서 `git merge <기준 브랜치>`를 실행하고 파일마다 처리한다:
   - **자동 생성 문서**(`<<file.moc>>` · `<<file.report>>` · `<<folder.past_reports>>` · `<<file.debt_status>>`): `git checkout --theirs -- <파일>`로 기준 브랜치 쪽을 받는다. 아래 4번에서 다시 만든다.
   - **`<<folder.current>>`의 글 문서:** 양쪽 사실을 **모두** 남긴다. 다른 작업이 적은 줄을 지우거나 한쪽 파일을 통째로 받지 않는다. frontmatter는 `updated`를 늦은 날로, `code`를 합친 목록으로 하고, `checked_commit`은 합친 커밋 뒤에 다시 적는다. 같은 사실이 서로 다르면 합쳐진 코드에서 맞는 쪽을 확인하고, 코드로 알 수 없으면 `git merge --abort` 후 사람에게 묻는다.
   - **데이터 · API 문서:** 양쪽을 합친 결과를 보여 주고 사람에게 묻는다 (`auto`여도 묻는다). 승인받으면 `lantern check-dbml`로 확인한다.
   - **코드와 그 밖의 파일:** 스스로 풀지 않는다. `git merge --abort` 후 충돌한 파일을 사람에게 알린다.

   모두 처리했으면 `lantern check` → `git add <파일>` → `git commit --no-edit` → `lantern work finish W-012`를 다시 실행한다.
4. 공통 마무리 + 맞추기 검사 + 보고 갱신:
   ```bash
   lantern close l-build --work W-012
   lantern scan
   lantern report
   ```
5. 마지막 보고: 증거 요약(할 일 · 커밋 · 테스트 · AC) · 반영한 것 · `scan`에서 나온 어긋남 · 부채 후보 · 구현 중 남긴 아이디어 카드 · `finish`가 낸 `⚠` (다른 브랜치에도 합치라는 안내는 사람이 정한다. 스스로 합치지 않는다) · 다음 할 일.
