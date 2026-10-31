"""References: material people bring in (company rules · terms · domain knowledge), inside the project or outside it.

`lantern ref index` hashes every section so a later change is noticed; the index of outside material
stays out of git, so a private document's titles never reach the repository. `lantern ref read` is the
one way the AI reads a section — outside material is never opened by the AI's own file tools.
"""

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
    assert "✔ lantern.yaml references.domain에 더함: ~/company" in out
    assert "문서 1개 · 절 6개 (새로 6 · 바뀜 0 · 사라짐 0)" in out and "+ 개인정보#개인정보 처리 지침#파기" in out
    assert yaml.safe_load((repo.root / "lantern.yaml").read_text(encoding="utf-8"))["references"]["domain"] == ["~/company"]
    private = repo.root / ".lantern/references.yaml"
    assert "~/company/개인정보.md" in private.read_text(encoding="utf-8")
    assert not (repo.root / "docs/0. 템플릿/_meta/references.yaml").exists()  # nothing about it inside the project
    assert "references.yaml" in (repo.root / ".lantern/.gitignore").read_text(encoding="utf-8").splitlines()

    _, out = repo("ref", "read", "개인정보#주문#보관 기간")
    assert "5년 동안 둔다." in out and "30일" not in out and "⚠" not in out
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
    assert "references.exclude: 개인정보#없는 절에 맞는 절이 더는 없습니다" in doctor
    assert "개인정보#파기에 맞는" not in doctor
