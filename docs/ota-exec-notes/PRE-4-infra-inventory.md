# PRE-4 build infra & OTA docs inventory

Date: 2026-07-24
Implementer: Codex

## Dependency check

- PRE-1/2/3 cards are `完成` on PLAN-OTA-EXEC.md before this claim.
- Working tree was clean at start of inventory (only this card's board write dirties EXEC).

## Required paths vs `git ls-files`

| Path | Tracked entries | Result |
|---|---:|---|
| CMakeLists.txt | 1 | OK |
| cmake/ | 16 | OK |
| vendor/ | 59 | OK |
| MDK-ARM_F435/cmake-generated/ | 25 | OK |
| .github/workflows/firmware-build.yml | 1 | OK |
| PLAN-OTA.md | 1 | OK |
| PLAN-OTA-DRAFT.md | 1 | OK |
| PLAN-OTA-REVIEW-LOG.md | 1 | OK |
| PLAN-OTA-EXEC.md | 1 | OK |
| PLAN-OTA-GUIDE.md | 1 | OK |

Missing: none. Total tracked required files: 107 (~5.07 MB working-tree bytes).

## Volume report (for user confirmation)

- `vendor/`: **2.78 MB**, 59 tracked files (AT32F435_437_DFP + CMSIS). Not large.
- Required tracked set overall: **~5.07 MB**.
- On-disk but **gitignored** build trees under `MDK-ARM_F435/cmake-generated/` (must stay out of git):
  - build-gcc ~95 MB
  - build-gcc-release ~11 MB
  - build-ci-test ~27 MB
  - build-ci-rel ~10 MB
- Ignore rules already present in `.gitignore` for those build dirs.

## Historical note

Card text assumed these paths were untracked. Repo history shows they were added in `9d9ea28` ("编写项目计划") and subsequent PRE-1..3 commits updated workflow/docs. PRE-4 therefore becomes a **verification + size report + residual board/docs evidence** task rather than a bulk first-time `git add`.

## Commit / push

- No additional bulk `git add` of the required set is needed (already tracked).
- `git remote -v` is empty in this workspace: **cannot** verify "push 后 Actions 干净 checkout 构建绿" here.
- User confirmation still needed if/when a remote is configured and push is desired; acceptance of the Actions-green clause requires post-push evidence outside this agent run.

## Commands run

```text
git ls-files -- <required paths>
git status --porcelain
git remote -v
# size walk of vendor + ignored build dirs
```
