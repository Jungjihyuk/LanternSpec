---
name: l-pr
description: 변경을 PR로 올리기 — lantern.yaml의 브랜치 방식(git.pr)에 맞는 방향을 찾아, 커밋과 작업 문서로 PR 제목 · 본문을 쓰고, 사람이 확인하면 push하고 gh로 PR을 만든다. 합치는 것은 하지 않는다. Use when the user asks to open a pull request.
invocation: manual
argument-hint: "[W-NNN]"
---

# /l-pr — 변경을 PR로 올리기

**목적:** 무엇이 왜 바뀌었는지 리뷰어가 알 수 있는 PR을 만든다. **push와 PR 생성은 사람이 확인한 뒤에만 하고, 합치는 것은 하지 않는다.**

입력: `$ARGUMENTS` — `W-012`(비우면 지금 브랜치의 작업).

## 1. 방향 정하기
<!-- lantern:if git.pr=deploy -->
이 프로젝트는 배포할 때 PR을 만든다: `<<git.base>>` → `<<git.deploy>>`. 그동안 `<<git.base>>`에 모인 작업이 모두 들어간다. 작업 브랜치에서 불렀으면 먼저 `/l-build`로 끝내서 `<<git.base>>`에 합치라고 안내한다.
<!-- lantern:endif -->
<!-- lantern:if git.pr=work -->
이 프로젝트는 작업마다 PR을 만든다: 작업 브랜치 → `<<git.base>>`. 작업 브랜치는 `lantern work list`에서 찾는다. `lantern work finish W-012`를 아직 안 했으면 먼저 한다 (기준 브랜치를 받아 테스트한다).
<!-- lantern:endif -->
<!-- lantern:if git.pr=none -->
이 프로젝트는 PR을 쓰지 않는 방식이다 (`git.pr: none`). 이번만 만들지 묻고, 그렇다면 어느 브랜치에서 어디로 올릴지 사람에게 묻는다. 계속 쓸 거면 `/l-init`을 다시 실행해 방식을 바꿀 수 있다고 알린다.
<!-- lantern:endif -->
아래에서 올리는 브랜치를 `<head>`, 받는 브랜치를 `<target>`이라 한다.

## 2. 확인 (하나라도 걸리면 멈추고 알린다)
```bash
gh auth status                                   # 안 되면 설치와 로그인(gh auth login)을 안내한다
git fetch origin
git status --short                               # 커밋하지 않은 변경이 있으면 먼저 커밋하게 한다
git log --oneline origin/<target>..<head>        # 비어 있으면 올릴 것이 없다
gh pr list --head <head> --base <target>         # 이미 있으면 그 주소를 보여 준다
git rev-list --count <head>..origin/<head>       # 0이 아니면 먼저 pull한다 (아직 push한 적 없는 브랜치면 건너뛴다)
git rev-list --count <head>..origin/<target>     # 0이 아니면 <target>의 변경을 먼저 합치자고 한다 (충돌은 사람이 푼다)
```
<!-- lantern:if build.test -->
`<head>`에서 `<<build.test>>`를 돌린다. 실패하면 PR을 만들지 않는다.
<!-- lantern:endif -->
<!-- lantern:if git.pr=deploy -->
`<head>`에 합친 코드를 실제로 돌려 확인했는지 사람에게 묻는다.
<!-- lantern:endif -->

## 3. 제목 · 본문 쓰기
`git log origin/<target>..<head>`의 `[W-012]` · `[W-012-T03]`으로 들어간 작업을 찾고, `git diff --stat origin/<target>...<head>`로 바뀐 범위를 본다. 작업의 `<<file.plan>>`에서 목적과 수락 기준을 읽는다.

- 저장소에 PR 양식(`.github/pull_request_template.md` 등)이 있으면 그 양식을 따르고 "연결 작업"만 더한다. 사내 규칙이 있으면 그것이 먼저다.
- **제목:** `[TYPE] 제목 [W-012]` — TYPE은 FEAT · FIX · DOCS · REFACTOR · REMOVE · CHORE · TEST · ENHANCE. 작업 ID를 넣어야 Squash로 합쳐도 작업을 찾을 수 있다. 작업이 여럿이면 `[DEPLOY] 제목 [W-012 · W-013]`.
- **본문:** 아래 형식으로 쓴다.
```markdown
<<pr.template>>
```
- 없는 내용은 지어내지 않는다. 확인하지 못한 수락 기준은 그렇다고 적는다.
- 제목과 본문에 AI가 작업했다는 표시(`Generated with …` · `Co-Authored-By` 등)를 넣지 않는다.
<!-- lantern:if docs.remote=local -->
- 문서를 원격에 올리지 않는 프로젝트다. 문서 내용을 옮겨 적거나 경로를 링크하지 말고, 작업 ID와 필요한 요약만 쓴다.
<!-- lantern:endif -->

## 4. 확인받고 올리기
먼저 공통 마무리를 돌린다. 문서가 바뀌면(지도 갱신 등) 커밋해서 이번 PR에 함께 넣는다 (커밋 메시지에도 AI가 작업했다는 표시를 넣지 않는다):
```bash
lantern close l-pr
```
방향 · 제목 · 본문 · push할 브랜치를 보여 주고 **"올릴까요?"라고 묻는다.** 승인하면 (본문을 파일로 남기지 않는다):
```bash
git push -u origin <head>
gh pr create --base <target> --head <head> --title "<제목>" --body-file - <<'EOF'
<본문>
EOF
```
PR 주소를 보여 준다.

## 5. 다음 안내
GitHub에서 확인하고 합치는 것은 사람이 한다.
<!-- lantern:if git.pr=deploy -->
- `<<git.base>>` → `<<git.deploy>>`는 **Create a merge commit**으로 합치기를 권한다. Squash로 합치면 두 브랜치의 이력이 갈라져 다음 PR에 같은 변경이 또 보이고, 할 일 ID도 사라질 수 있다.
- 합친 뒤에는 배포 쪽 변경을 받아 둔다: `git checkout <<git.base>>` · `git pull origin <<git.base>>` · `git merge origin/<<git.deploy>>`
<!-- lantern:endif -->
<!-- lantern:if !git.pr=deploy -->
- Squash로 합치면 제목의 작업 ID로 작업을 찾을 수 있지만, 커밋의 할 일 ID는 사라질 수 있다.
- 합친 뒤에는: `git checkout <target>` · `git pull origin <target>` · 작업 브랜치 정리 `git branch -d <head>` (Squash로 합쳤으면 합쳐진 것을 확인하고 `-D`)
<!-- lantern:endif -->
