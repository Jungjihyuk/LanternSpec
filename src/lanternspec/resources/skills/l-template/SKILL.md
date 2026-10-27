---
name: l-template
description: 양식 만들기 · 다듬기 · 옮기기 — 읽기 좋은 글 시안(문서 · 캡처 · 설명)을 빈칸 양식({{칸}} · > [!guide])으로 만들고(new), 기존 양식의 가독성을 점검해 고치기 전 · 후로 개선안을 보여 주고(refine), 바뀐 양식에 맞춰 기존 문서의 구조만 옮긴다(migrate — 내용은 잃지 않음). Use when a new document type is needed, a template should be improved, or docs must move to a new template version.
invocation: model
argument-hint: "new | refine <양식> | migrate [<양식> | <문서 경로>]"
---

# /l-template — 양식 만들기 · 다듬기 · 옮기기

**목적:** 사용자에게 **잘 읽히는 글의 구조**를 양식으로 만들고, 계속 다듬고, 기존 문서를 새 양식으로 옮긴다. 양식은 `docs/0. 템플릿/`에 있고 사용자가 자기에게 맞게 다듬어 가는 곳이다.

입력: `$ARGUMENTS` — `new` · `refine 기획` · `migrate` · `migrate 기획` · `migrate "2. 작업/W-012 …/기획.md"` · `migrate "5. 기존 문서/옛 기획.md"`

## 양식 규칙
- 채울 칸 `{{칸 이름}}`, 필수 칸 `{{칸 이름 (필수)}}` — `|`는 표를 깨뜨리므로 쓰지 않는다
- 칸 이름에 `date` · `time` · `title` 금지 (Obsidian 기본 템플릿이 바꿔 버림)
- 작성 안내는 `> [!guide] …` (다 쓰면 지워도 됨). 칸마다 **🟦 원본 칸 / 🔗 가져오는 칸**을 안내에 표시
- 스크립트가 채우는 값은 `${id}` · `${today}` · `${name}` · `${work_id}` · `${links}` 등 (손대지 않는다)
- 맨 위 "한눈에 보기" 칸은 필수: `> [!abstract] 한눈에 보기` + `> {{… (필수)}}`
- 공통 frontmatter: `id · type · status · created · updated · links · template · template_version`(+ 양식에만 `based_on`)
- 맨 아래 `<!-- lantern:template-only -->` 뒤 `## 변경 기록` 표 (문서에는 복사되지 않음)

## 만들기 `new`
1. 시안에서 구조를 뽑는다: 제목 · 섹션 · 표 · 그림 자리 · 한눈에 보기. 파일이 있으면 뼈대부터:
   ```bash
   lantern template new "<양식 이름>" --from "<시안 파일>"     # 미리보기만 (아직 저장 안 함)
   ```
2. 내용은 지우고 빈칸 `{{칸}}`과 `> [!guide]` 안내로 바꾼다. 칸마다 원본 / 가져오는 칸 표시.
3. 공통 frontmatter를 붙이고 `type`은 `enums.yaml`의 `doc_type` 중 하나 (새 종류면 추가를 제안).
4. **미리보기 → 승인 → 저장:** `lantern template new "<이름>" --from "<시안>" --apply` 또는 다듬은 내용을 `docs/0. 템플릿/<이름>.md`로 저장 → `lantern template lint "<이름>"`
5. 새 양식으로 문서를 만들 때는 `lantern scaffold custom "<양식>" "<docs 안 경로.md>"`

## 다듬기 `refine <양식>`
1. 가독성 점검:
   ```bash
   lantern template lint "<양식>"
   lantern template usage "<양식>"     # 실제 문서에서 늘 비어 있는 칸
   ```
   더 볼 것: 한눈에 보기가 있나 · 표나 그림이 나은 곳을 글로 쓰고 있나 · 칸 이름이 바로 이해되나 · 너무 긴가
2. 개선안을 **고치기 전 · 후**로 나란히 보여 준다.
3. 승인 → 저장 → 버전 올림. 버전은 바뀐 내용을 보고 스크립트가 정하고 사람은 확인만 한다:
   ```bash
   lantern template level "<양식>"                       # patch(안내만) · minor(칸 추가) · major(칸 삭제 · 이름 변경)
   lantern template bump "<양식>" --auto --note "<무엇이 바뀌었나>"
   ```
4. major면 옮기기를 제안한다 (`lantern template outdated "<양식>"`로 대상 확인).

## 옮기기 `migrate` — 내용을 잃지 않는 규칙
1. 대상 보기: `lantern template outdated` (아직 쓰는 문서만 — `3. 현재 상태` · 진행 중 작업. 끝난 작업 · `5. 기존 문서`는 제안하지 않는다. 원하면 하나씩 직접)
2. 옛 칸 → 새 칸 대응표를 만든다 (이름이 바뀐 칸 · 합쳐진 칸 · 나뉜 칸). 미리보기:
   ```bash
   lantern template migrate "<양식 | 문서>" [--map "옛 칸=새 칸" …]
   ```
3. 대응되는 내용은 새 자리로 옮기고, **대응되지 않는 내용은 지우지 않고** 문서 맨 아래 `## 📦 옮기지 못한 내용`에 모은다 → 사람이 정리한다.
4. 문서별로 바뀌는 점을 보여 주고 승인 → `--apply`. git이 안전망이다.
5. **기존 문서(5. 기존 문서)를 우리 양식으로:** `lantern template migrate "5. 기존 문서/<문서>.md" --to <양식> --dest "<docs 안 새 경로.md>" [--apply]` — 원본은 그대로 두고 새 문서를 만든다. `기존 문서 지도`의 새 위치 칸을 채운다.

## 공통 마무리
```bash
lantern close l-template
```
