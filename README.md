# C8E-Devtool

Evaluation harness measuring how AI coding tools perform on the **Tina4 framework** —
out of the box, and with the assist layers Code Infinity is developing on top of them.

## Purpose

Code Infinity builds tools intended to make AI coding agents better at Tina4 work:

- **Dev kits** — editor setup + shared agent config (extensions, `AGENTS.md`, rules files)
- **Tina4 MCP** — hosted fine-tuned coding models at `mcp.tina4.com/mcp`
  (`tina4_code`, `tina4_review` tools, Bearer-token auth via the Tina4 Developer Portal)

This repo answers one question per tool: **do these layers actually improve the agent's
output on Tina4 tasks, and by how much?**

## Method

Each coding tool is evaluated in three configurations, same task set, same machine:

| Config | Setup |
|--------|-------|
| **A — Vanilla** | Tool as installed. No extras. |
| **B — + Dev kit** | A + devkit applied (extensions, agent rules, `.vscode` settings). |
| **C — + MCP** | B + Tina4 MCP connected and routing rule installed. |

A fixed set of Tina4 tasks (routes, ORM models, templates, migrations, queues) is given
to the tool's AI agent in each configuration. Results are compared across configurations
for correctness, Tina4 idiom fidelity, and how much manual correction the output needs.

Alongside agent performance, the assist layers themselves are verified: installer
behavior against its documented claims, config deployment, per-language
IntelliSense/diagnostics delta.

## Current target

**Google Antigravity** (v1.107.0, Windows) — first tool under evaluation.

- Dev kit: `antigravity-devkit` (setup scripts, `extensions.txt`, agent config)
- MCP: Tina4 Developer Portal token → `mcp.tina4.com/mcp`

## Future targets

Other AI coding tools (Cursor, VS Code + Copilot, Windsurf, …) — same A/B/C method,
same task set where the tool allows it.

## Findings policy

**Log-only.** Findings are recorded in this repo with version stamps and reproduction
steps. Nothing is fixed in the tools, dev kits, or frameworks under test from here;
fixes are decided and made outside this project.

## Layout

```
C8E-Devtool/
├── README.md            # this file — frozen scope; findings never go here
├── findings-log.md      # living log: all findings + evaluation progress table
├── tasks/               # frozen query spec + grading checklist
├── graders/             # parent harness: serves generated app, checks routes/CRUD/idioms
│   └── reference-app/   # known-good impl the grader calibrates against (9/9, 6/6)
├── hub/                 # operator console (tina4 app, :7000) — browse + drive every run
├── baselines/           # machine/tool state snapshots per config (A/B/C)
└── antigravity/         # one dir per tool under test — open the IDE here
    ├── a-vanilla/
    │   └── run-1..3/    # fresh workspace per run; agent works inside run-N
    ├── b-devkit/
    │   └── run-1..3/    # devkit deployed into each run dir (-TargetRepo)
    └── c-mcp/
        └── run-1..3/
```

Each run gets a clean `run-N/` workspace — an agent opening a dir containing a previous
run's code is no longer producing a first output.

## Config sequencing (one-way)

Extensions and MCP settings are IDE-global, and headless uninstall is unverified —
assume install is one-way per machine. Therefore all **A** runs complete before the
devkit is applied, and all **B** runs before the MCP is connected. Per-repo config
(`AGENTS.md`, `.agents/`, `.vscode/`) is deployed per run dir and does not leak
across configs.
