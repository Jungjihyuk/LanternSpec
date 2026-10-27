# LanternSpec 개발용 명령 — `make` 또는 `make help`로 목록을 본다.
SHELL := /bin/bash
.PHONY: help check release

help:
	@echo "make check                   확인 네 가지 — 포맷 · 린트 · 타입 검사 · 테스트"
	@echo "make release VERSION=0.2.0   배포 — 안전 확인 → 확인 네 가지 → CHANGELOG에 버전 찍기 → uv version → 커밋 · 태그 → push"
	@echo "                             (태그가 올라가면 GitHub Actions가 PyPI에 올린다. 먼저 /release-notes로 바뀐 점을 정리한다)"

check:
	uv run ruff format --check src tests
	uv run ruff check src tests
	uv run pyright
	uv run pytest -q

release:
	@test -n "$(VERSION)" || { echo "✖ 버전을 주세요: make release VERSION=0.2.0"; exit 1; }
	@test "$$(git branch --show-current)" = main || { echo "✖ main 브랜치에서만 배포합니다"; exit 1; }
	@test -z "$$(git status --porcelain)" || { echo "✖ 커밋하지 않은 변경이 있습니다 — 커밋하거나 치운 뒤 다시"; exit 1; }
	@git fetch -q origin main && git merge-base --is-ancestor origin/main HEAD \
		|| { echo "✖ GitHub의 main에 이쪽에 없는 커밋이 있습니다 — pull 먼저 (아직 안 올린 커밋은 괜찮다: 배포 push 때 같이 올라간다)"; exit 1; }
	@! git rev-parse -q --verify "refs/tags/v$(VERSION)" >/dev/null || { echo "✖ 태그 v$(VERSION)가 이미 있습니다"; exit 1; }
	$(MAKE) check
	uv run python scripts/changelog.py $(VERSION)
	uv version $(VERSION)
	git commit -qam "Release $(VERSION)"
	git tag -a v$(VERSION) -m "LanternSpec $(VERSION)"
	@echo "✔ 커밋 'Release $(VERSION)' · 태그 v$(VERSION)"
	@read -r -p "GitHub에 push할까요? 태그가 올라가면 PyPI 배포가 시작됩니다 [y/N] " ans; \
	if [ "$$ans" = y ]; then git push origin main "v$(VERSION)"; \
	else echo "push하지 않았습니다. 나중에: git push origin main v$(VERSION)"; fi
