"""References: material people bring in (company rules · terms · domain knowledge), inside the project or outside it.

`lantern ref index` hashes every section so a later change is noticed; the index of outside material
stays out of git, so a private document's titles never reach the repository. `lantern ref read` is the
one way the AI reads a section — outside material is never opened by the AI's own file tools.
"""

import json
import subprocess
import sys
from pathlib import Path

import yaml

from conftest import init_project

LAW = """# 개인정보 처리 지침

## 회원
### 보관 기간
탈퇴 후 30일 동안 둔다.

## 주문
### 보관 기간
5년 동안 둔다.

## 파기
지체 없이 지운다.
"""


def _outside(text: str = LAW) -> Path:
    folder = Path.home() / "company"
    folder.mkdir(exist_ok=True)
    (folder / "개인정보.md").write_text(text, encoding="utf-8")
    return folder


def test_outside_material_is_indexed_out_of_git_and_read_by_section(repo):
    init_project(repo)
    folder = _outside()
    _, out = repo("ref", "index", "domain", "~/company")
    assert "✔ .lantern/references.yaml에 적음 (밖의 자료는 git에 올리지 않음): domain ~/company" in out
    assert "문서 1개 · 절 6개 (새로 6 · 바뀜 0 · 사라짐 0)" in out and "+ 개인정보#개인정보 처리 지침#파기" in out
    assert "company" not in (repo.root / "lantern.yaml").read_text(encoding="utf-8")  # the outside path stays out of git
    private = yaml.safe_load((repo.root / ".lantern/references.yaml").read_text(encoding="utf-8"))
    assert private["sources"] == {"domain": ["~/company"]} and "~/company/개인정보.md" in private["documents"]
    assert not (repo.root / "docs/0. 템플릿/_meta/references.yaml").exists()  # nothing about it inside the project
    assert "references.yaml" in (repo.root / ".lantern/.gitignore").read_text(encoding="utf-8").splitlines()

    _, out = repo("ref", "read", "개인정보#주문#보관 기간")
    assert "5년 동안 둔다." in out and "30일" not in out and "⚠" not in out
    assert "(개인정보.md) -->" in out and "company" not in out  # where it lives isn't printed
    code, out = repo("ref", "read", "개인정보#보관 기간", ok=False)
    assert code != 0 and "2번 나옵니다" in out and "개인정보#개인정보 처리 지침#회원#보관 기간" in out
    code, out = repo("ref", "read", "개인정보#보관기한", ok=False)
    assert code != 0 and "비슷한 제목: 개인정보#개인정보 처리 지침#회원#보관 기간" in out

    (folder / "개인정보.md").write_text(LAW.replace("5년", "10년"), encoding="utf-8")
    _, out = repo("ref", "read", "개인정보#주문#보관 기간")
    assert "⚠ 색인 뒤에 바뀌었습니다" in out
    _, doctor = repo("doctor", ok=False)
    assert "domain: 색인 뒤에 바뀌었거나 색인한 적이 없는 문서: 개인정보 (3)" in doctor  # the section and the ones above it
    _, out = repo("ref", "index", "domain", "~/company")
    assert "더함" not in out and "~ 개인정보#개인정보 처리 지침#주문#보관 기간" in out and "+ " not in out
    _, doctor = repo("doctor", ok=False)
    assert "참고 자료 1곳 — 색인이 최신입니다" in doctor


def test_inside_material_is_indexed_in_the_docs_for_the_team(repo):
    init_project(repo)
    (repo.root / "rules").mkdir()
    (repo.root / "rules/API.md").write_text("# API\n## 오류 응답\n늘 problem+json으로 답한다.\n", encoding="utf-8")
    repo("ref", "index", "rules", "rules")
    shared = yaml.safe_load((repo.root / "docs/0. 템플릿/_meta/references.yaml").read_text(encoding="utf-8"))
    assert shared["documents"]["rules/API.md"]["kind"] == "rules"
    assert not (repo.root / ".lantern/references.yaml").exists()
    _, out = repo("ref")
    assert "✔ rules  rules  (안) · 문서 1개 · 색인됨" in out


def test_a_long_section_lists_its_parts_to_read_one_at_a_time(repo):
    init_project(repo)
    body = "\n".join(f"{i}번째 줄" for i in range(200))
    _outside(f"# 법\n## 1장\n{body}\n## 2장\n{body}\n")
    repo("ref", "index", "domain", "~/company")
    _, out = repo("ref", "read", "개인정보")
    assert "줄입니다 — 한 부분씩 읽으세요" in out and 'lantern ref read "개인정보#법"' in out
    _, out = repo("ref", "read", "개인정보#법")
    assert 'lantern ref read "개인정보#법#1장"' in out and "0번째 줄" not in out
    _, out = repo("ref", "read", "개인정보#1장")
    assert "199번째 줄" in out


def test_check_points_out_structure_that_cant_be_read_in_parts(repo):
    init_project(repo)
    _outside("# 법\n#### 보관\n" + "본문\n" * 50)
    code, out = repo("ref", "check", "~/company", ok=False)
    assert code == 1 and "'보관': 제목 급을 건너뛰었습니다 (# → ####)" in out
    _outside(LAW)
    _, out = repo("ref", "check", "~/company")
    assert "✔ ~/company/개인정보.md · 절 6개" in out


def test_doctor_notices_missing_paths_and_exclusions_that_match_nothing(repo):
    init_project(repo)
    _outside()
    repo("ref", "index", "terms", "~/company")
    repo("profile", "set", "references.rules=[~/없는 폴더]", "references.exclude=[개인정보#없는 절, 개인정보#파기]")
    _, doctor = repo("doctor", ok=False)
    assert "references.rules: ~/없는 폴더가 없습니다" in doctor
    assert "references.rules: ~/없는 폴더는 프로젝트 밖의 자료인데 lantern.yaml은 git에 올라갑니다" in doctor
    assert "references.exclude: 개인정보#없는 절에 맞는 절이 더는 없습니다" in doctor
    assert "개인정보#파기에 맞는" not in doctor


def test_an_outside_path_written_in_lantern_yaml_is_moved_out_of_git(repo):
    init_project(repo)
    _outside()
    repo("profile", "set", "references.terms=[~/company]")
    _, out = repo("ref", "index", "terms", "~/company")
    assert "✔ git에 올라가는 lantern.yaml에서 뺌: references.terms ~/company" in out
    assert "company" not in (repo.root / "lantern.yaml").read_text(encoding="utf-8")
    _, out = repo("ref")
    assert "✔ terms  ~/company  (밖) · 문서 1개 · 색인됨" in out


RULES = """# API 규칙

## 오류 응답
늘 problem+json으로 답한다.

### 예시
```
# 이 줄은 제목이 아니다
```

## 이름 짓기
엔드포인트는 복수 명사로 쓴다.

## 로그
개인정보를 로그에 남기지 않는다.
"""


def _parts_with_rules(repo):
    init_project(repo, "--kind", "service", "--external", "no", "--languages", "python,typescript")
    for part, manifest in (("backend", "pyproject.toml"), ("web", "package.json")):
        (repo.root / part).mkdir()
        (repo.root / part / manifest).write_text("[project]\nname='b'\n" if part == "backend" else '{"name": "w"}\n', encoding="utf-8")
    repo("install")
    repo("parts", "add", "backend")
    repo("parts", "add", "web")
    (repo.root / "rules").mkdir()
    (repo.root / "rules/API.md").write_text(RULES, encoding="utf-8")
    repo("ref", "index", "rules", "rules")


def test_approved_inside_rules_go_word_for_word_into_the_agents_md_of_their_scope(repo):
    _parts_with_rules(repo)
    _, out = repo("ref", "tag", "API#오류 응답", "--scope", "backend", "--strength", "must")
    assert "✔ API#API 규칙#오류 응답: backend · must → lantern upgrade" in out
    repo("ref", "tag", "API#이름 짓기", "--scope", "all", "--strength", "should")
    repo("ref", "tag", "API#로그", "--scope", "typescript")
    code, out = repo("ref", "tag", "API#로그", "--scope", "go", ok=False)
    assert code != 0 and "모르는 범위 go" in out
    repo("upgrade")
    backend = (repo.root / "backend/AGENTS.md").read_text(encoding="utf-8")
    assert "## 사내 규칙" in backend and "### 반드시 지킴" in backend
    assert (
        "#### 오류 응답\n늘 problem+json으로 답한다.\n\n##### 예시\n```\n# 이 줄은 제목이 아니다\n```" in backend
    )  # headings moved down, code kept
    assert "이름 짓기" not in backend and "로그" not in backend
    root = (repo.root / "AGENTS.md").read_text(encoding="utf-8")
    assert "### 되도록 따름" in root and "#### 이름 짓기\n엔드포인트는 복수 명사로 쓴다." in root and "오류 응답" not in root
    web = (repo.root / "web/AGENTS.md").read_text(encoding="utf-8")
    assert "개인정보를 로그에 남기지 않는다." in web  # a language rule goes to the parts of that language
    assert "lantern ref rules" not in root + backend + web  # nothing outside: no pointer
    _, doctor = repo("doctor", ok=False)
    assert "사내 규칙이 승인한 것과 다릅니다" not in doctor

    (repo.root / "rules/API.md").write_text(RULES.replace("problem+json", "RFC 9457"), encoding="utf-8")
    _, doctor = repo("doctor", ok=False)
    assert "backend/AGENTS.md: 사내 규칙이 승인한 것과 다릅니다 — lantern upgrade" in doctor
    repo("ref", "index", "rules", "rules")  # the approvals survive a new index
    repo("ref", "exclude", "API#로그")
    repo("upgrade")
    assert "RFC 9457" in (repo.root / "backend/AGENTS.md").read_text(encoding="utf-8")
    assert "로그에 남기지" not in (repo.root / "web/AGENTS.md").read_text(encoding="utf-8")
    assert yaml.safe_load((repo.root / "lantern.yaml").read_text(encoding="utf-8"))["references"]["exclude"] == ["API#로그"]


def test_outside_rules_stay_out_of_committed_files_and_are_printed_on_request(repo):
    _parts_with_rules(repo)
    folder = Path.home() / "company"
    folder.mkdir(exist_ok=True)
    (folder / "보안.md").write_text("# 보안\n## 비밀 값\n비밀 값은 코드에 두지 않는다.\n## 검토\n두 사람이 본다.\n", encoding="utf-8")
    repo("ref", "index", "rules", "~/company")
    repo("ref", "tag", "보안#비밀 값", "--scope", "all", "--strength", "must")
    repo("ref", "tag", "보안#검토", "--scope", "backend", "--strength", "should")
    repo("ref", "exclude", "보안#없는 절", ok=False)
    repo("upgrade")
    committed = "".join((repo.root / p).read_text(encoding="utf-8") for p in ("AGENTS.md", "backend/AGENTS.md", "lantern.yaml"))
    assert yaml.safe_load((repo.root / "lantern.yaml").read_text(encoding="utf-8"))["references"]["outside_rules"] is True
    assert "비밀 값" not in committed and "검토" not in committed and "company" not in committed and "보안" not in committed
    assert "`lantern ref rules`를 실행해" in (repo.root / "AGENTS.md").read_text(encoding="utf-8")
    assert "`lantern ref rules backend`를 실행해" in (repo.root / "backend/AGENTS.md").read_text(encoding="utf-8")
    _, out = repo("ref", "rules")
    assert "비밀 값은 코드에 두지 않는다." in out and "두 사람이 본다." not in out
    _, out = repo("ref", "rules", "backend")
    assert "### 비밀 값" not in out and "### 되도록 따름" not in out and "## 되도록 따름" in out and "두 사람이 본다." in out

    hook = subprocess.run(
        [sys.executable, "-m", "lanternspec", "hook", "session-start"],
        cwd=str(repo.root),
        input=json.dumps({"session_id": "s", "source": "compact"}),
        capture_output=True,
        text=True,
    )
    assert "[프로젝트 밖에 둔 사내 규칙 — 반드시 지킴]" in hook.stdout and "비밀 값은 코드에 두지 않는다." in hook.stdout
    assert "두 사람이 본다." not in hook.stdout

    repo("ref", "exclude", "보안#검토")
    assert "보안#검토" in (repo.root / ".lantern/references.yaml").read_text(encoding="utf-8")  # an outside title stays out of git
    _, out = repo("ref", "rules", "backend")
    assert "이 컴퓨터에는 프로젝트 밖에 둔 사내 규칙이 없습니다" in out

    (repo.root / ".lantern/references.yaml").unlink()  # a teammate without the outside material
    repo("upgrade")
    assert "`lantern ref rules`를 실행해" in (repo.root / "AGENTS.md").read_text(encoding="utf-8")  # the same AGENTS.md for everyone
    code, out = repo("ref", "rules", ok=False)
    assert code == 1 and "이 컴퓨터에는 아직 없습니다 — 담당자에게 자료 위치를 받아 /l-ref rules <경로>로 들이세요" in out
    _, doctor = repo("doctor", ok=False)
    assert "이 프로젝트는 밖에 둔 사내 규칙을 따르는데" in doctor

    repo("profile", "set", "references.outside_rules=false")  # people turn it off
    repo("upgrade")
    assert "lantern ref rules" not in (repo.root / "AGENTS.md").read_text(encoding="utf-8")


def test_should_rules_become_pointers_when_agents_md_is_over_budget(repo):
    _parts_with_rules(repo)
    long = "# 긴 규칙\n## 반드시\n짧다.\n## 참고\n" + "되도록 이렇게 한다.\n" * 600
    (repo.root / "rules/긴.md").write_text(long, encoding="utf-8")
    repo("ref", "index", "rules", "rules")
    repo("ref", "tag", "긴#반드시", "--scope", "backend", "--strength", "must")
    repo("ref", "tag", "긴#참고", "--scope", "backend", "--strength", "should")
    repo("upgrade")
    backend = (repo.root / "backend/AGENTS.md").read_text(encoding="utf-8")
    assert "#### 반드시\n짧다." in backend
    assert '- 참고 — `lantern ref read "긴#긴 규칙#참고"`' in backend and "되도록 이렇게 한다." not in backend


GLOSSARY_ROWS = (
    "| 회원 | 가입한 사람 | 유저, 사용자 | |\n| 회원 정보 | 회원의 이름 · 연락처 | 정보 | |\n| 결제 | 돈을 받는 일 | payment | |\n"
)


def _glossary(repo, rows=GLOSSARY_ROWS):
    path = repo.root / "docs/3. 현재 상태/규칙/용어집.md"
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace("|---|---|---|---|\n", "|---|---|---|---|\n" + rows, 1), encoding="utf-8")


def test_the_glossary_comes_with_the_project_and_check_points_out_words_to_avoid(repo):
    init_project(repo)
    assert (repo.root / "docs/3. 현재 상태/규칙/용어집.md").exists()
    _glossary(repo)
    plan = repo.root / "docs/3. 현재 상태/기능 목록.md"
    plan.write_text(
        plan.read_text(encoding="utf-8")
        + "\n유저가 가입한다.\n회원 정보를 고친다.\n`사용자` 테이블\n```\n사용자 = 1\n```\nPayment API, payments-v2\n",
        encoding="utf-8",
    )
    code, out = repo("check", ok=False)
    assert "'유저' — '회원'로 쓰세요 (용어집.md)" in out and "가입한 사람" in out
    assert "'정보' — '회원 정보'" not in out  # the term's own words don't count
    assert "'사용자'" not in out  # inside code
    assert "'payment' — '결제'로 쓰세요" in out and out.count("'payment'") == 1  # whole words only, any case
    assert out.count("'유저'") == 1  # the glossary itself, which lists the word, isn't checked

    _, out = repo("ref", "terms")
    assert "| 회원 | 가입한 사람 | 유저, 사용자 | all | 프로젝트 |" in out


def test_company_terms_are_approved_into_the_index_and_win_over_the_project_glossary(repo):
    init_project(repo)
    _glossary(repo)
    folder = Path.home() / "company"
    folder.mkdir(exist_ok=True)
    (folder / "사내 용어.md").write_text(
        "# 사내 용어\n## 회원\n고객사와 계약한 사람. 멤버라고 하지 않는다.\n## 정산\n월말 계산.\n", encoding="utf-8"
    )
    repo("ref", "index", "terms", "~/company")
    _, out = repo("ref", "term", "사내 용어", "회원", "--avoid", "멤버", "--meaning", "고객사와 계약한 사람")
    assert "✔ 사내 용어: 회원 (쓰지 말 표현: 멤버)" in out
    code, out = repo("ref", "term", "사내 용어", "없는 말", "--avoid", "x", ok=False)
    assert code != 0 and "사내 용어에 없는 말이라는 말이 없습니다" in out
    _, out = repo("ref", "terms")
    assert "| 회원 | 고객사와 계약한 사람 | 멤버 | all | 사내 |" in out and "가입한 사람" not in out
    assert "⚠ 프로젝트 용어집에도 다른 뜻으로 있습니다 — 사내 것을 따릅니다: 회원" in out
    assert "사내 용어" not in (repo.root / "lantern.yaml").read_text(encoding="utf-8")  # outside: nothing in git

    features = repo.root / "docs/3. 현재 상태/기능 목록.md"
    features.write_text(features.read_text(encoding="utf-8") + "\n멤버가 로그인한다.\n유저도 쓴다.\n", encoding="utf-8")
    _, out = repo("check", ok=False)
    assert "'멤버' — '회원'로 쓰세요 (사내 용어집)" in out and "'유저'" not in out  # the company's term replaces the project's

    repo("ref", "index", "terms", "~/company")  # approved terms survive a new index
    _, out = repo("ref", "terms")
    assert "| 회원 | 고객사와 계약한 사람 |" in out
    repo("ref", "term", "사내 용어", "회원", "--off")
    _, out = repo("ref", "terms")
    assert "| 회원 | 가입한 사람 |" in out


def test_an_existing_project_gets_the_glossary_on_upgrade(repo):
    init_project(repo)
    path = repo.root / "docs/3. 현재 상태/규칙/용어집.md"
    path.unlink()
    _, out = repo("upgrade")
    assert "ℹ 새로 만들 문서: 3. 현재 상태/규칙/용어집.md → lantern scaffold init" in out and not path.exists()
    repo("scaffold", "init")
    assert "## 용어" in path.read_text(encoding="utf-8")
