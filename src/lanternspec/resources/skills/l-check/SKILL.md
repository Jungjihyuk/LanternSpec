---
name: l-check
description: 양식 검사 — docs/ 문서의 필수 칸 · enums.yaml 값 · 깨진 링크 · 남은 {{칸}} · 옛 템플릿 버전 · ID 중복 · 문서 길이 · 할 일 형식을 lantern check로 검사하고 결과를 설명하고 고칠 방법을 제안한다. Use before committing, after a template version changed, or when the user asks whether docs follow the templates.
invocation: model
argument-hint: "[문서 경로 | --changed | --epic W-NNN]"
---

# /l-check — 양식 검사

**목적:** 판정은 스크립트가 한다. 너는 **결과를 설명하고 고칠 방법을 제안**한다.

## 처리 순서
1. 검사한다:
   ```bash
   lantern check                 # 전체
   lantern check --changed       # 커밋 전: 바뀐 문서만
   lantern check "<경로>"         # 문서 하나
   lantern check --epic W-012    # 수락 기준 규칙 (뜻이 하나인가 · 확인할 수 있는가)
   ```
2. 결과를 묶어서 설명한다: **✖ 오류**(깨진 링크 · 틀린 값 · ID 중복 · 사라진 필수 칸) → **⚠ 경고**(필수 빈칸 · 긴 문서 · 크게 바뀐 양식) → **ℹ 참고**(빈 칸 · ❓ 확인 필요 · 새 칸 생긴 양식).
3. 고칠 방법을 제안한다:
   - 필수 빈칸 → 채울 내용을 묻거나, 모르면 `❓ 확인 필요`
   - 틀린 값 → `docs/0. 템플릿/_meta/enums.yaml`의 값으로 (새 값이 필요하면 enums.yaml에 추가 제안)
   - 깨진 링크 → 맞는 문서 이름 · 경로 제안
   - 양식이 크게 바뀜(major) → `/l-template migrate "<문서>"`
   - 긴 문서 → 검사가 짚은 칸을 별도 문서로 나누고 링크
   - `❓ 확인 필요` → 목록으로 보여 주고 답을 받을 수 있는지 묻는다
4. 사용자가 원하면 고친다. 템플릿 구조(칸 · 제목)는 바꾸지 않는다. 고쳤으면 다시 `lantern check`로 확인한다.

문서를 고쳤으면 공통 마무리 `lantern close l-check`.
