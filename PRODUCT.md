# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

**Primary: the developer or tech lead who installs Camarón on a multi-repo project.** They operate it from the
desktop app (run plan units with Claude Code or Codex, interviews, quality, libraries, board, decisions) and validate
the result in the portal (read, review, confirm AI drafts). They come to it to onboard people, understand an
inherited system, or document the architecture and flows of a project spread over several repositories.

Teammates who only read the portal exist, but they were not confirmed as the design priority.

## Product Purpose

Camarón is a local kit (CLI, terminal wizard, desktop app and web portal) that turns a multi-repo project into
documentation people can explore, review and maintain. The agent reads the code, Camarón splits the work into
session-sized units and keeps progress between sessions, and a person validates the result. Everything lands in
`cam-docs/`: a versioned project brain where code, architecture, domain and decisions are explained for humans and
agents alike.

Success, in the kit's own priority order:

1. Installing already gives value almost without AI (repos, code graph, C4 draft, plan, portal from static analysis).
2. Then AI completes it (interviews, drafting, architecture, domain, flows, upkeep when code changes).
3. Everything the AI adds stays reviewable and traceable.

## Positioning

**Traceable trust.** Every AI-written page is a draft until a person confirms it; each claim carries the sources it
came from (`x-sources`); a page turns suspect as soon as the code it cites changes. Confirmed pages are the source of
truth for people and for agents.

## Operating Context

- **Two surfaces, split roles.** The desktop app (`camaron app`, Electron, one window per project) is where the user
  *operates*: plan, interviews, team, quality, libraries, wikis, machine, board, decisions. It is keyboard-first
  (Ctrl K palette, `g` + letter jumps, a guided tour). The portal (`camaron up`, a browser on `127.0.0.1:8080`, or
  "Ver portal" from the app) is where the user *reads*: docs, C4 architecture, board, stories, live plan, quality and
  review. The portal runs no machine action; it only writes the board, with a per-session token.
- Both are served by the project's local server and share one UI kit (`.camarones/ui`: theme, base components, i18n).
  The portal may also be deployed on an internal network.
- Used next to agent sessions (Claude Code, Codex, OpenCode, Gemini CLI), which read the same docs through the
  `camarones` MCP server.
- Runs on macOS, Windows and Linux.

## Capabilities and Constraints

- Page trust: `draft` → `confirmed`, and back to needing reconfirmation when sources change; blocks a person wrote are
  never rewritten.
- Plan units move through `todo`, `doing`, `done`, `blocked` (including awaiting approval) and `dropped`.
- Both UIs are React 19 + Vite; their builds (`portal/app-build`, `desktop/renderer-build`) are committed and CI fails
  when they differ from the source. A UI change ships with its rebuilt bundle.
- Projects made by any 3.x or 4.x kit must keep opening; UI changes cannot assume a fresh project.
- Terminology lives in `cam-docs/docs/domain/glossary.md` (unit, plan, run, autopilot, board, ADR, trust levels).

## Brand Commitments

Binding (confirmed by the user):

- **Spanish and English at parity.** Every user-facing string exists in `es` and `en`.
- **Local, no CDN.** Fonts and libraries are served from the kit; the UI makes no request to third parties and
  nothing about the project leaves the machine.

Incumbent but **not** binding (open decisions, not defaults to defend):

- The intern-shrimp voice (`AGENTS.md` §3, `README.md`).
- The Cofundo-derived visual system with its Camarón adaptations
  (`.claude/skills/cofundo-design-system/`, `CAMARON.md`).

## Evidence on Hand

- Real screenshots and recordings: `.github/media/` (`portal-docs`, `portal-review`, `portal-c4`, `app-*.png`,
  `app-tour.gif`, `workflow.gif`, `hero.svg`).
- The mark: the shrimp favicon `.camarones/portal/app/public/favicon.svg`; `scripts/icons.py` renders the desktop
  icons from it.
- User guides in both languages: `.camarones/templates/docs/guides/` and `.camarones/templates/docs/i18n/es/guides/`.
- End-to-end bench: the Spring PetClinic sandbox (`scripts/sandbox.py`).
- Absent: customer testimonials, usage metrics, pricing, case studies. Do not fabricate them.

## Product Principles

1. **Value before AI.** A surface shows what static analysis already knows before it asks for a model.
2. **Trust is legible.** Draft, confirmed, suspect and the sources behind a claim are visible next to the content they
   qualify.
3. **Read in the portal, operate in the app.** Keep the split; don't put machine actions in the reader.
4. **One clear next step.** Each screen leads with the next action and sensible defaults.
5. **Local and bilingual by default.**

## Accessibility & Inclusion

- Text keeps 4.5:1 contrast in light and dark themes (`.camarones/ui/theme/tokens.test.js`).
- The desktop app is fully usable with the keyboard alone.
- `prefers-reduced-motion` is honoured.
- States are never told by colour alone; they always carry their word.
