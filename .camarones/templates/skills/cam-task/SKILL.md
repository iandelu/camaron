---
name: cam-task
description: Start here for any code change (feature, fix, refactor) in {{PROJECT_NAME}} — read cam-docs first, judge difficulty, test first, verify, pass the guardrails, state the impact, then open linked code and docs PRs.
---

# Make a code change

Every code change goes through these steps, in this order. Run commands from the workspace root (the folder that holds
the service repos and `{{CAM}}`) unless a step says otherwise.

1. **Set up the change.**
   - `<ITEM>`: the board item's id as the board shows it (e.g. `WI-12`). No board item: leave out `--item` below and
     name the repos with `--repo`; no card moves.
   - `git fetch` in each service repo you will change, then, from the workspace root and
     without the three worktree variables defined below in this step (with them the kit reads the docs worktree's
     copy of the board and of the change records, not the ones in `{{CAM}}` that people see):
     `{{CLI}} change start "<title>" --item <ITEM> [--repo <repo>]… [--files <repo>:<path>,…]` (`--files` adds the
     pages that cite the files you expect to touch). Run every `{{CLI}} change …` command the same way.
   - It checks everything before writing anything: the repos are there with no uncommitted work, and the card may
     start (the start gate). Never `--force`: a refusal names the uncommitted work, unfinished dependencies or a file
     clash with work in progress → stop and give the person the reason; the `--force` hint in the refusal is for
     people, and only the person decides `--force`.
   - It creates `cam/<id>-<slug>` in each repo from `origin/<default branch>`, or adopts a clean feature branch already
     checked out (say so to the person), opens the docs worktree `.cw/<id>` and prints the docs to read and the next
     step. You move your own card by running the change commands: `change start` → In Progress, `change link`
     (`cam-ship`) → In Review, `change close` → Done once the person merged, or Ready with `--abandon`. Never
     `board move` for these steps.
   - `<id>` is the id it prints (`WI-12` → `wi-12`). Each repo line shows its branch and its `<base>` (e.g.
     `origin/main`); the docs line shows the docs' `<base>`, the branch `{{CAM}}` had checked out. Later,
     `{{CLI}} change status <id>` shows them again. Edit docs only in `.cw/<id>/docs/`, never in `{{CAM}}docs/`.
   - From step 2 on, start each step by recording its phase (in brackets after its name):
     `{{CLI}} change phase <id> <phase>`. A phase never goes back: when a later step sends you back (a fix after
     `verify`), keep the later phase and carry on.
   - **On the worktree** means `{{CLI}}` with three variables set; without them it misreads the layout and reports
     false errors: `CAMARONES_ROOT="$PWD/.cw/<id>" CAMARONES_WORKSPACE="$PWD" CAMARONES_STATE_ROOT="$PWD/{{CAM}}." {{CLI}} <command>`
     (PowerShell: set the three with `$env:`, run, then remove them).
2. **Read the docs first** [`docs`] with `cam-docs-lookup`: the feature's terms, the files you expect to touch,
   `overview/removed.md`. Before changing any code, summarise what they say with citations `[path#section]`, and flag
   draft or suspect pages and anything that contradicts the code.
3. **Score the difficulty** [`assess`] with `cam-difficulty`. Its level decides step 4.
4. **Design and plan as the level says** [`plan`]: low → a short plan in chat; medium → a written plan the person
   approves before any code; high → a spec and a plan, both approved, then a split into board items.
5. **Implement test-first** [`code`]: for each behaviour a failing test, watch it fail, make it pass. Commit with the
   repo's own conventions.
6. **Update the docs in the worktree** [`docs-update`] with `cam-docs-update`, adapted: edit `.cw/<id>/docs/`
   instead of `{{CAM}}docs/`, run its `{{CLI}}` commands on the worktree, skip its `llms`, `checkpoint` and `mark-documented`, and
   do not use the MCP's `propose_edit` (it writes to the main checkout). A board item: link it to the pages you
   updated, on the worktree, as `cam-ship` guardrail 8 says. Then commit the docs locally, leaving out the four derived
   files the kit's commands rewrite (`docs/.status.json`, `docs/.work/fresh.json`, `docs/llms.txt`,
   `docs/llms-full.txt`):
   `git -C .cw/<id> add -A -- . ":(exclude)docs/.status.json" ":(exclude)docs/llms.txt" ":(exclude)docs/llms-full.txt" ":(exclude)docs/.work/fresh.json"`,
   then `git -C .cw/<id> commit -m "docs: <title>"`. Commit every later docs edit the same way: verification and the
   guardrails read commits, not the working tree. A tree is **clean** when `git status --porcelain` lists nothing, or,
   in `.cw/<id>`, nothing but the four derived files.
7. **Verify** [`verify`] with `cam-verify`.
8. **Ship** [`ship`] with `cam-ship`: guardrails, impact, one question, linked draft PRs.
9. **Retro** [`retro`] with `cam-retro`.

## With superpowers

When superpowers' skills are available, use them for the generic steps: step 4 → `brainstorming` and `writing-plans`
(medium and high), step 5 → `test-driven-development`, any failure → `systematic-debugging`. Without them, follow the
steps above as written: write the failing test, watch it fail, make it pass. Camarón's own steps 1–3 and 6–9 are
never skipped either way. While a change is open, `cam-ship` replaces `finishing-a-development-branch`.

Step 1's branches and docs worktree are the change's workspace: create no other worktree (they already satisfy
`using-git-worktrees`), and keep the code on its branch in the person's own checkout. Specs and plans stay in chat or
go into `.cw/<id>/docs/.work/plans/`, never at the workspace root or in a service repo.

## When to ask the person

- To approve the plan (medium and high) before any code.
- When the difficulty level goes up.
- When a step skill says to stop and ask (a flaky check, a failed guardrail).
- When the start gate refuses the board item.
- Once, before opening the PRs (`cam-ship`).

If the change stops before the PRs (split into other items, or a "no" to "Open the PRs?"), tell the person the card is
still In Progress; if they give the change up, `{{CLI}} change close <id> --abandon` puts it back in Ready.

Otherwise keep going. Never merge. Never write `x-confirmed`; never edit `<!-- human -->` blocks or pages with
`x-owner: human`.
