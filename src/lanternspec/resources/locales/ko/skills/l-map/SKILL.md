---
name: l-map
description: 문서 지도(MOC) 갱신 — 지금 폴더 상태 · 템플릿 · 명령 정보로 docs/<<file.moc>>의 폴더 블록(역할 · 파일 · 템플릿 · 명령, 단계별 작업 보기)을 다시 쓴다. 사람이 쓴 부분은 l-map 표시 밖이라 덮어쓰지 않는다. Use when folders or documents were added, moved or renamed.
invocation: model
---

# /l-map — 문서 지도 갱신

**목적:** MOC를 지금 폴더 상태에 맞게 다시 만든다. 전부 스크립트가 한다.

```bash
lantern map
```

- `<!-- l-map:start -->` ~ `<!-- l-map:end -->` 사이만 다시 쓴다. 사람이 쓴 내용은 그 **밖**에 두라고 안내한다.
- 바뀐 것이 없으면 파일을 건드리지 않는다.
- 결과를 한 줄로 알린다: 폴더 수 · 진행 중 작업 수 · 승인 대기 작업.
- 깨진 링크가 의심되면 `lantern check`를 이어서 권한다.

다른 스킬의 공통 마무리(`lantern close`)가 이미 `map`을 부르므로, 보통은 직접 부르지 않아도 된다.
