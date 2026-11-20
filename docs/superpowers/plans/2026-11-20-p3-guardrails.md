# P3 — guardrails installed and blocking: plan

**Spec:** `docs/superpowers/specs/2026-11-17-core-turning-point-design.md` §4 "P3", §5 step 3, decision D5.
**Difficulty (cam-difficulty):** 4, medium — signals: `auth` (a secrets path: gitleaks, forbidden paths), `weak-docs`
(the cam-docs pages that cite the kit are withheld: its checkout is behind), `hotspot` (`install_state`, `setup`);
inferred: git hooks run on every commit of the person's repos, on three OSes.

## Goal

After `camaron setup` (and `repair`), in every repo of the workspace and in cam-docs, with **no tracked file written**:

1. a commit message loses an AI co-author trailer or a "Generated with Claude Code" line, a push that still carries one
   is refused, and staged secrets stop the commit (the kit repo's own `.githooks`, made generic);
2. a push of cam-docs runs `camaron check` and stops on an error;
3. Claude Code's commit and PR attribution is off in each repo's and the workspace's local settings;
4. `camaron guard gate` fails on a leaked secret, a forbidden path, an AI trailer, a **new** high or critical
   vulnerability in a dependency file the change touches, a red Sonar quality gate and (opt-in) a library the change
   adds or bumps that is a major version behind. A check that could not run is "not run", never green.

## Design

| Piece | Where | What |
|---|---|---|
| Hook scripts | `lib/githooks/` | `dispatch` (one file, copied to every git hook name) and `kit/{commit-msg,pre-commit,pre-push}` (the checks, also this repo's `.githooks`, kept byte-equal by a test) |
| Machine folder | `~/.camarones/githooks/` | the dispatcher under each hook name, `kit/`, and `kit-cmd` (how to run this kit). Rewritten by every install and repair |
| Per repo | local git config only | `core.hooksPath` = that folder; `camaron.chain` = the hooks folder the repo had (`.husky/_`, a global path), none = its `.git/hooks`; `camaron.check` = `true` for cam-docs |
| Pure rules | `lib/domain/guard.py` | the AI-credit pattern, forbidden paths, the attribution setting, the verdict of the checks, majors behind |
| Side effects | `lib/adapters/guard.py` (`services.guard`) | install, status and uninstall of the hooks and the settings; the gate checks (gitleaks, `osv`, `sonar`, `inventory` + `latest`) |
| CLI | `camaron guard install | status | gate | uninstall` | exit 0 pass, 1 a check failed, 3 nothing failed but a check could not run |
| Wiring | `app/setup.py` (`wire_one`, `wire_umbrella`), `install_state` (`repair`, `drift`), `uninstall` | idempotent; `guard: {install: false}` in `workspace.yaml` opts a project out |

### D5 — the chain

The dispatcher runs the kit's check for that hook first, then the repo's own hook of the same name: the folder
`camaron.chain` names (relative to the repo's top, as husky sets `.husky/_`), else `<git-common-dir>/hooks`
(`pre-commit` framework, hand-written hooks). The kit's check can stop the operation; the repo's exit code is the
hook's. `pre-push` and `post-rewrite` get stdin once and both parts read it. A tool that rewrites `core.hooksPath`
later (husky's `prepare`) shows up as drift: `doctor` lists it and `repair` re-chains it. The one trade-off: git runs
`post-index-change` and `reference-transaction` on every index or ref write and `fsmonitor-watchman` speaks on stdout,
so the dispatcher does not answer those three: a repo's own hook of one of them stops running.

### Decisions the AI took

- `camaron check` runs on push for **cam-docs only**, and not from a linked worktree (`.cw/<id>`, where it reads the
  wrong layout without the three `change` variables). In a service repo it checks docs, not the code being pushed, and
  it is slow and noisy there. The service repos get the trailer refusal on push; the secret scan of the pushed range is
  `guard gate`.
- A hook whose tool is missing (no gitleaks, no kit) **warns on stderr and lets the git operation go**, as the kit
  repo's own pre-commit does: a missing scanner must not brick `git commit`. The gate is the strict one.
- The gate reads "new" vulnerabilities by scanning the touched files at the base and at HEAD and keeping what the base
  lacked, so touching a manifest never blames the change for old debt.
- The outdated check sends library names to public registries, so it is off until `guard: {outdated: true}` (team) or
  `--latest` (this run). Off is "n/a", not "not run".
- Attribution is written to `.claude/settings.local.json` (git-ignored through `.git/info/exclude` in a service repo;
  already ignored in cam-docs and the workspace folder): `{"attribution": {"commit": "", "pr": ""}}`, the key of Claude
  Code ≥ 2.0.62 (`includeCoAuthoredBy` is deprecated). Checked against the installed 2.1.326's docs, not its code.

## Tasks (test first)

1. `domain/guard.py` + `tests/test_guard_domain.py`.
2. Hook scripts + `tests/test_guard_hooks.py`: trailer drop, push refusal, gitleaks on commit, a repo with its own hooks
   (`.git/hooks`, husky's `.husky/_`, stdin through the chain, the repo's `commit-msg` sees the cleaned message),
   idempotence, uninstall restores.
3. `adapters/guard.py` install / status / uninstall + settings + `services.guard`.
4. Gate checks + `tests/test_guard_gate.py`.
5. `commands/guard.py` + catalog snapshot.
6. Wiring in setup, repair, drift, uninstall (+ sandbox `traces`) + `tests/test_guard_setup.py`.
7. Docs, README, guides en/es, version `4.97.0`.

## Not in this change

`change gate` (P2 step 4) calls `guard.gate`; hooks for Codex; the per-repo Claude Code retrieval hooks (P1, D3);
Sonar token storage UI (the gate reads the token `creds` already holds).
