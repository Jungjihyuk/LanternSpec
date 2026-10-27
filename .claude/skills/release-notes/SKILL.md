---
name: release-notes
description: LanternSpec 저장소 전용 — 마지막 배포 태그 이후의 변경을 읽어 CHANGELOG(영어 · 한국어)의 [Unreleased]와, 사용법이 바뀌었으면 README(영어 · 한국어)를 고친다. 초안을 보여 주고 승인받은 뒤 쓰고 커밋한다. 배포(make release) 직전에 부른다.
disable-model-invocation: true
---

# /release-notes — 바뀐 점 정리 (배포 전)

**목적:** 마지막 배포 이후 **사용자에게 보이는 변화**를 CHANGELOG에 모으고, README가 지금 동작과 맞게 한다.
버전 찍기 · 커밋 · 태그 · push는 하지 않는다 — 그건 `make release VERSION=…`가 한다.

## 1. 읽기
```bash
git describe --tags --abbrev=0                 # 마지막 배포 태그 (예: v0.1.0)
git log --reverse --format='%h %s%n%b' <태그>..HEAD
git diff --stat <태그>..HEAD
```
- `CHANGELOG.md` · `CHANGELOG.ko.md`의 `## [Unreleased]` 칸을 읽는다. **이미 적힌 항목은 다시 쓰지 않는다.**
- 커밋 메시지만으로 애매하면 그 커밋의 변경(`git show <해시>`)을 본다.

## 2. 고르기
- **넣는 것:** 사용자가 겪는 변화 — 새 명령 · 옵션, `/l-*` 스킬의 동작 · 질문, 만들어지는 문서 · 설정, 출력 문구, 고친 버그.
- **빼는 것:** 이 저장소 안의 일 — 테스트, 리팩터링, CI · 배포 워크플로, AGENTS.md, README만 고친 커밋.
- 분류: **추가 / 바뀜 / 고침** (영어: Added / Changed / Fixed). 해당 없는 칸은 만들지 않는다.
- 스킬 · 템플릿 · 규칙 · Obsidian 설정처럼 **프로젝트 폴더에 설치되는 것**이 바뀌었으면 칸 맨 위에 업그레이드 안내 한 줄을 둔다:
  `업그레이드: uv tool upgrade lanternspec → 프로젝트마다 lantern upgrade (…)` (이미 있으면 괄호 안만 맞춘다)

## 3. 쓰는 법
- 한 항목 = 한 줄: `- **짧은 제목** — 무엇이 어떻게 바뀌었나`. 문장 중간에서 줄을 바꾸지 않는다.
- 명세 번호(H-4 · BU-03 등)나 내부 파일 이름 대신, 사용자가 보는 이름으로 쓴다.
- 영어판과 한국어판은 **같은 항목 · 같은 순서**. 각 언어로 자연스럽게 쓴다 (설명은 그 언어로만).

## 4. README
- 바뀐 동작이 README에 적힌 내용(설치 · 빠른 시작 · 스킬 표 · CLI 한눈에 · 각 절)과 어긋나면 `README.md` · `README.ko.md`를 같이 고친다.
- 새 명령은 "CLI 한눈에"에 더한다. README에 없던 기능이면 알맞은 절에 짧게 더한다.

## 5. 보여 주고 승인받기
쓰기 전에 초안을 보여 준다:
- CHANGELOG에 더할 항목 (한국어판 기준, 영어판은 같은 내용이라고 한 줄)
- README에서 고칠 곳 (절 이름과 바뀌는 문장)
- **다음 버전 추천과 이유** — 아래 "버전 정하는 기준"대로. 어느 항목 때문에 그 자리를 올리는지 한 줄로 적는다

## 6. 쓰고 확인 · 커밋
승인받으면 쓰고:
```bash
rm -rf dist && uv build >/dev/null && uvx twine check dist/*   # README가 PyPI에서 잘 보이는지
git add CHANGELOG.md CHANGELOG.ko.md README.md README.ko.md
git commit -m "Update changelog and README for <다음 버전>"
```
커밋 메시지는 영어로, AI 표시(Co-Authored-By 등) 없이. 끝으로 다음 단계를 한 줄로 알린다: `make release VERSION=<다음 버전>`

---

## 버전 정하는 기준
버전은 `주.부.수`(예: 0.1.1). 자리를 올리면 오른쪽 자리는 0으로 돌아간다. 판단의 열쇠는 하나다:
**"이미 쓰던 프로젝트가 `uv tool upgrade lanternspec` → `lantern upgrade`만으로 그대로 동작하나?"**

**지금 (0.x — 1.0 전)**

| 올리는 자리 | 언제 | 예 |
|---|---|---|
| 가운데 (0.1.3 → 0.2.0) | **아니요** — 사용자가 뭔가 고치거나 옮겨야 한다 | `lantern.yaml` 키 · 값의 이름 변경 · 삭제, 문서 폴더 · 파일 · frontmatter 칸 이름 변경, 명령 · 옵션의 삭제 · 이름 변경, `enums.yaml` 역할(role) 삭제 |
| 마지막 (0.1.0 → 0.1.1) | **예** — 그 밖의 모든 것 | 새 명령 · 새 기능, 스킬 질문 · 문구 개선, 버그 수정 |

- 가운데 자리를 올릴 때는 CHANGELOG 그 버전 칸 맨 위에 **"옮기는 법"**(무엇을 어떻게 고치면 되는지)을 적는다.
- 사람이 큰 이정표로 가운데 자리를 올리겠다고 하면 그대로 따른다.

**1.0 이후** — 표준 유의적 버전: 호환이 깨지면 첫째 자리, 새 기능은 가운데 자리, 고침만 있으면 마지막 자리.
