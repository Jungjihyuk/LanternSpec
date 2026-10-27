"""lantern check · --epic · DBML."""

from conftest import docs, fill, fill_plan, init_project, work_dir
from lanternspec.work import dbml


def test_check_finds_each_kind_of_problem(repo):
    init_project(repo)
    repo("scaffold", "idea", "하나")
    d = docs(repo)
    idea = next((d / "1. 아이디어").glob("IDEA-001*"))
    fill(idea, [('kind: "기능"', 'kind: "기능x"'), ("{{관련 문서}}", "[[없는 문서]] · [[3. 현재 상태/기능 목록]]")])
    copy = d / "1. 아이디어" / "IDEA-001 복사.md"
    copy.write_text(idea.read_text(encoding="utf-8"), encoding="utf-8")
    code, out = repo("check", ok=False)
    assert code == 1
    assert "kind: '기능x'는 아이디어 유형 값이 아닙니다" in out
    assert "깨진 링크: [[없는 문서]]" in out
    assert "[[3. 현재 상태/기능 목록]]" not in out.split("깨진 링크")[-1].split("\n")[0]
    assert "ID IDEA-001가 다른 문서와 겹칩니다" in out
    assert "필수 칸이 비어 있습니다: {{한 줄 요약 (필수)}}" in out
    _, js = repo("check", "--json", str(idea), ok=False)
    assert '"broken-link"' in js


def test_check_structure_length_and_template_versions(repo):
    init_project(repo)
    repo("profile", "set", "check.max_lines=40")
    repo("scaffold", "work", "작업")
    plan = fill_plan(repo, "W-001")
    fill(plan, [("## 범위 밖", "## 범위 바깥")])
    long_doc = docs(repo) / "3. 현재 상태/시스템 구조.md"
    fill(long_doc, [("{{주요 흐름}}", "\n".join(f"- 흐름 {i}" for i in range(60)))])
    tmpl = docs(repo) / "0. 템플릿/기획.md"
    fill(tmpl, [("template_version: 1.0.0", "template_version: 2.0.0")])
    code, out = repo("check", ok=False)
    assert "양식 '기획'의 필수 칸 '## 범위 밖'" not in out  # 범위 밖 has no required blank
    assert "양식 '기획'이 1.0.0 → 2.0.0로 크게 바뀌었습니다" in out
    assert "'## 주요 흐름' 칸이" in out and "줄입니다 (기준 40줄)" in out
    fill(plan, [("## 왜", "## 이유")])
    code, out = repo("check", str(plan), ok=False)
    assert code == 1 and "필수 칸 '## 왜'이 사라졌습니다" in out
    # minor bump → info only
    fill(plan, [("## 이유", "## 왜")])
    fill(tmpl, [("template_version: 2.0.0", "template_version: 1.1.0")])
    _, out = repo("check", str(plan))
    assert "새 칸이 생겼습니다" in out


def test_check_task_file_rules(repo):
    init_project(repo)
    repo("profile", "set", "project.team=team", "project.members=[지혁]")
    repo("scaffold", "work", "작업")
    fill_plan(repo, "W-001")
    repo("scaffold", "doc", "W-001", "할 일")
    tf = work_dir(repo, "W-001") / "할 일.md"
    text = tf.read_text(encoding="utf-8").replace(
        "- [ ] W-001-T01 {{할 일 (필수)}} [크기:: {{S · M · L}}] [기준:: {{AC-1}}]",
        "- [ ] W-001-T01 하나 [크기:: XL] [기준:: AC-9] [먼저:: T02]\n- [ ] W-001-T02 둘 [크기:: S] [먼저:: T01]\n- [ ] W-001-T02 셋",
    )
    tf.write_text(text, encoding="utf-8")
    code, out = repo("check", str(tf), ok=False)
    assert "할 일 ID가 겹칩니다: W-001-T02" in out
    assert "크기는 S · M · L" in out and "크기가 없습니다" in out
    assert "수락 기준 AC-9이 기획.md에 없습니다" in out
    assert "먼저 끝나야 할 일이 순환합니다" in out
    assert "담당이 없습니다" in out


def test_dropped_idea_needs_reason(repo):
    init_project(repo)
    repo("scaffold", "idea", "하나")
    idea = next((docs(repo) / "1. 아이디어").glob("IDEA-001*"))
    fill(idea, [('status: "새 아이디어"', 'status: "버림"')])
    _, out = repo("check", str(idea))
    assert "버린 아이디어에는 이유 한 줄이 필요합니다" in out


def test_epic_rules(repo):
    init_project(repo)
    repo("scaffold", "work", "작업")
    fill_plan(
        repo,
        "W-001",
        ac_lines=(
            "- [ ] AC-1 상황: 홈에서 · 행동: 누르면 · 결과: 빠르게 열린다\n"
            "- [ ] AC-2 버튼을 누르면 열린다\n"
            "- [ ] AC-4 행동: 저장하면 · 결과: 목록 또는 상세가 보인다"
        ),
    )
    _, out = repo("check", "--epic", "W-001")
    assert "AC-1: 확인하기 어려운 말 '빠르게'" in out
    assert "AC-2: 상황 · 행동 · 결과 형식이 아닙니다" in out
    assert "AC-4: 결과가 여러 뜻으로 읽힙니다" in out
    assert "AC-4: 번호가 순서대로가 아닙니다" in out
    repo("profile", "set", "plan.ac_format=simple")
    _, out = repo("check", "--epic", "W-001")
    assert "AC-2: '~하면 ~된다' 형식이 아닙니다" not in out  # "누르면 열린다" is the simple form
    assert "AC-2: 상황 · 행동 · 결과" not in out


def test_dbml_parse_check_render():
    src = """
// 사용자
Table users as U {
  id int [pk, increment]
  email varchar(255) [not null, unique, note: '로그인 이메일. 예: a@b.com']
  Note: '회원'
  indexes {
    email [unique]
  }
}
Table posts {
  id int [pk]
  user_id int [ref: > U.id]
  "title" varchar
}
Ref: posts.user_id > users.id
Ref fk { posts.id - users.nope }
Enum status { draft
  done }
"""
    schema = dbml.parse(src)
    assert set(schema.tables) == {"users", "posts"}
    assert schema.tables["users"].note == "회원"
    assert schema.enums["status"] == ["draft", "done"]
    problems = dbml.check(schema)
    assert any("'users.nope' 컬럼이 없습니다" in m for _, _, m in problems)
    assert not any("U" == m for _, _, m in problems)
    md = dbml.to_mermaid(schema)
    assert "users {" in md and "int id PK" in md and "posts }o--|| U" in md or "posts }o--|| users" in md
    dic = dbml.to_dictionary(schema)
    assert "| users | email | `varchar(255)` | not null, unique | 로그인 이메일 | a@b.com |" in dic


def test_dbml_syntax_errors():
    schema = dbml.parse("Table a {\n  id\n  id int\n}\nTable a { x int }\nfoo bar\n")
    msgs = [m for _, _, m in dbml.check(schema)]
    assert any("타입이 없습니다" in m for m in msgs)
    assert any("두 번 정의" in m for m in msgs)
    assert any("알 수 없는 문장" in m for m in msgs)
    assert any("짝이 맞지" in m for m in [m for _, _, m in dbml.check(dbml.parse("Table a {\n id int\n"))])


def test_sql_to_dbml_and_diff(tmp_path):
    (tmp_path / "001.sql").write_text(
        'CREATE TABLE IF NOT EXISTS "users" (id SERIAL PRIMARY KEY, email TEXT NOT NULL UNIQUE, tmp int);\n'
        "CREATE TABLE orders (id bigint, user_id int, total numeric(10,2) DEFAULT 0,\n"
        "  PRIMARY KEY (id), FOREIGN KEY (user_id) REFERENCES users(id));\n",
        encoding="utf-8",
    )
    (tmp_path / "002.sql").write_text(
        "ALTER TABLE users DROP COLUMN tmp;\nALTER TABLE orders ADD COLUMN status text NOT NULL DEFAULT 'new';\n"
        "ALTER TABLE orders RENAME COLUMN total TO amount;\nCREATE TABLE junk (id int);\nDROP TABLE junk;\n",
        encoding="utf-8",
    )
    real = dbml.from_sql(sorted(tmp_path.glob("*.sql")))
    assert set(real.tables) == {"users", "orders"}
    assert [c.name for c in real.tables["orders"].columns] == ["id", "user_id", "amount", "status"]
    assert real.tables["orders"].column("id").pk
    assert any(r.left == ("orders", "user_id") and r.right == ("users", "id") for r in real.refs)
    text = dbml.to_dbml(real)
    again = dbml.parse(text)
    assert dbml.diff(again, real) == []
    assert not [p for p in dbml.check(again) if p[0] == "error"]
    doc = dbml.parse("Table users {\n id int [pk]\n email text\n name text\n}\n")
    diffs = "\n".join(dbml.diff(doc, real))
    assert "테이블 'orders'이 마이그레이션에는 있는데" in diffs
    assert "'users.name'이 DBML에만" in diffs
    assert "users.id' 타입" not in diffs  # serial ≈ int


def test_dbml_render_into_data_doc(repo):
    init_project(repo)
    schema = docs(repo) / "3. 현재 상태/데이터/schema.dbml"
    schema.write_text("Table users {\n  id int [pk]\n  email text [note: '이메일']\n}\n", encoding="utf-8")
    repo("dbml", "render")
    text = (docs(repo) / "3. 현재 상태/데이터/데이터.md").read_text(encoding="utf-8")
    assert "erDiagram" in text and "| users | email | `text` |" in text
    before = text.split("## ERD")[0]
    repo("dbml", "render")
    assert (docs(repo) / "3. 현재 상태/데이터/데이터.md").read_text(encoding="utf-8").split("## ERD")[0] == before
    schema.write_text("Table users {\n  id\n}\n", encoding="utf-8")
    code, _ = repo("dbml", "render", ok=False)
    assert code == 1
