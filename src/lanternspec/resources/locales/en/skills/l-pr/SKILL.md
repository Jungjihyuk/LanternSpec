---
name: l-pr
description: Open a pull request for the changes — find the direction that fits the branch flow in lantern.yaml (git.pr), write the title and body from the commits and work documents, and once the person confirms, push and open the PR with gh. It never merges. Use when the user asks to open a pull request.
invocation: manual
argument-hint: "[W-NNN]"
---

# /l-pr — open a pull request

**Purpose:** make a PR that tells a reviewer what changed and why. **Push and create it only after the person confirms, and never merge.**

Input: `$ARGUMENTS` — `W-012` (when empty, the work of the current branch).

## 1. Find the direction
<!-- lantern:if git.pr=deploy -->
This project opens a PR when it deploys: `<<git.base>>` → `<<git.deploy>>`. Every work gathered in `<<git.base>>` goes in. If called from a work branch, tell the person to finish it with `/l-build` and merge it into `<<git.base>>` first.
<!-- lantern:endif -->
<!-- lantern:if git.pr=work -->
This project opens a PR for each work: work branch → `<<git.base>>`. Find the work branch with `lantern work list`. If `lantern work finish W-012` hasn't run yet, run it first (it brings in the base branch and tests).
<!-- lantern:endif -->
<!-- lantern:if git.pr=none -->
This project's flow doesn't use PRs (`git.pr: none`). Ask whether to open one just this once, and if so, from which branch into which. If they want this from now on, say `/l-init` run again can change the flow.
<!-- lantern:endif -->
Below, the branch going up is `<head>` and the receiving branch is `<target>`.

## 2. Check (stop and say so if any of these fails)
```bash
gh auth status                                   # if not, explain installing it and logging in (gh auth login)
git fetch origin
git status --short                               # uncommitted changes: have them committed first
git log --oneline origin/<target>..<head>        # empty: nothing to send
gh pr list --head <head> --base <target>         # already exists: show its address
git rev-list --count <head>..origin/<head>       # not 0: pull first (skip for a branch never pushed)
git rev-list --count <head>..origin/<target>     # not 0: suggest merging <target>'s changes first (the person resolves conflicts)
```
<!-- lantern:if build.test -->
Run `<<build.test>>` on `<head>`. If it fails, don't open the PR.
<!-- lantern:endif -->
<!-- lantern:if git.pr=deploy -->
Ask the person whether the code merged into `<head>` was actually run and checked.
<!-- lantern:endif -->

## 3. Write the title and body
Find the works that went in from `[W-012]` · `[W-012-T03]` in `git log origin/<target>..<head>`, and the extent of the change from `git diff --stat origin/<target>...<head>`. Read each work's purpose and acceptance criteria in its `<<file.plan>>`.

- If the repository has a PR template (`.github/pull_request_template.md` and so on), follow it and only add "Linked works". Company rules come first.
- **Title:** `[TYPE] title [W-012]` — TYPE is FEAT · FIX · DOCS · REFACTOR · REMOVE · CHORE · TEST · ENHANCE. The work ID keeps the work findable even after a squash merge. With several works, `[DEPLOY] title [W-012 · W-013]`.
- **Body:** use this format.
```markdown
<<pr.template>>
```
- Don't make up what isn't there. If an acceptance criterion wasn't checked, say so.
- Don't put any mark that AI did the work (`Generated with …` · `Co-Authored-By` and so on) in the title or body.
<!-- lantern:if docs.remote=local -->
- This project keeps documents off the remote. Don't copy their content or link their paths; write only work IDs and the summary needed.
<!-- lantern:endif -->

## 4. Confirm, then send
First run the common wrap-up. If it changes documents (the map and so on), commit them so they go in this PR:
```bash
lantern close l-pr
```
Show the direction · title · body · branch to push and **ask "Send it?"** Once approved (no body file is left behind):
```bash
git push -u origin <head>
gh pr create --base <target> --head <head> --title "<title>" --body-file - <<'EOF'
<body>
EOF
```
Show the PR's address.

## 5. What's next
Reviewing and merging on GitHub is up to the person.
<!-- lantern:if git.pr=deploy -->
- For `<<git.base>>` → `<<git.deploy>>`, recommend **Create a merge commit**. A squash merge splits the two branches' histories, so the next PR shows the same changes again, and task IDs may be lost.
- After merging, bring the deploy side's changes back: `git checkout <<git.base>>` · `git pull origin <<git.base>>` · `git merge origin/<<git.deploy>>`
<!-- lantern:endif -->
<!-- lantern:if !git.pr=deploy -->
- After a squash merge the work ID in the title still finds the work, but task IDs in the commits may be lost.
- After merging: `git checkout <target>` · `git pull origin <target>` · clean up the work branch with `git branch -d <head>` (after a squash merge, confirm it went in, then `-D`)
<!-- lantern:endif -->
