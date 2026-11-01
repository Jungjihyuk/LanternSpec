---
id: CUR-api
type: current
status: ${current_status.active}
created: ${today}
updated: ${today}
links: []
template: API
template_version: 1.0.1
based_on: 1.0.1
code: []
checked_commit: ""
---
# 📘 API

> [!abstract] 한눈에 보기
> {{API 형태와 인증 방식 한 문장 (필수)}}

> [!guide] 요청 · 응답의 자세한 모양은 **코드가 기준**이다.
> - 코드에서 문서를 뽑을 수 있으면(OpenAPI 등) 그 결과물을 링크한다
> - 여기에는 엔드포인트 목록과 공통 규칙만 둔다

## 공통 규칙
- 인증: {{인증 방식}}
- 오류 형식: {{오류 형식}}

## 엔드포인트
| 메서드 | 경로 | 하는 일 | 출처 작업 |
|---|---|---|---|
| {{GET}} | `{{/path}}` | {{하는 일}} | {{작업 링크}} |

<!-- lantern:template-only -->
## 변경 기록
| 버전 | 날짜 | 무엇이 바뀌었나 |
|---|---|---|
| 1.0.0 | 2026-10-27 | 기본 양식 |
| 1.0.1 | 2026-11-02 | 안내를 읽기 쉽게 다듬음 (긴 안내는 여러 줄로, 기호와 내부 이름은 말로) |
