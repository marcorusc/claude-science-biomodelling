# claude-science-biomodelling

Biomodelling specialists for Claude Science

Four agent profiles and six skills for driving the [`mcp-biomodelling-servers`](https://github.com/marcorusc/mcp-biomodelling-servers)
stack (NeKo -> MaBoSS -> PhysiCell, plus BioMASS) from Claude Science.

Ported from the Claude Code specialists in
`github.com/marcorusc/agentic_system_for_modelling/.claude/`.

## What is in here

| Profile | Connector | Job |
|---|---|---|
| `NETWORK_CURATOR` | `neko` | Build, inspect, repair and export OmniPath/SIGNOR networks |
| `BOOLEAN_DYNAMICS_MODELER` | `maboss` | Import a NeKo handoff, simulate WT and mutants |
| `ODE_MODELER` | `biomass` | Author and validate BioMASS ODE models |
| `MULTICELLULAR_CONFIGURATOR` | `physicell` | Configure PhysiCell/PhysiBoSS (never runs it) |

| Skill | Purpose |
|---|---|
| `neko-workflow`, `maboss-workflow`, `physicell-workflow` | Per-server operational guides (2.5.2) |
| `biomass-authoring` | Text2Model reaction syntax and editing, with four reference files |
| `biomodelling-handoff` | Cross-server transport: bundles, session volatility, server quirks |
| `biomodelling-pipeline` | Lead-side dispatch harness with per-stage output schemas |

Each profile is **curated**: one connector only, with `delete_session` and
`clean_generated_files` (and `close_session` on BioMASS) excluded at tool level,
so a specialist cannot destroy sessions or generated artifacts.

## Layout

```
agents/<PROFILE>.md     one per specialist: frontmatter (display name,
                        description, connector, excluded tools, skills) plus
                        the full system prompt as the body
skills/<skill>/         SKILL.md and any reference files
install.py              reads the two directories above and provisions them
```

The markdown files **are** the definitions — there is no generated manifest, so
editing a prompt or a skill list and re-running `install()` is the whole update
loop. This mirrors `.claude/agents/` and `.claude/skills/` in the Claude Code
repo, with the frontmatter keys this platform needs instead.

## Install

You need the four MCP connectors attached to your account first (`neko`, `maboss`,
`biomass`, `physicell`) — the installer skips any profile whose connector is
missing. The servers behind them are
[`marcorusc/mcp-biomodelling-servers`](https://github.com/marcorusc/mcp-biomodelling-servers).

The profiles also list skills this repo does not ship: `figure-style`, which is
built into Claude Science, and the `mcp-*` per-tool reference skills
(`mcp-neko*`, `mcp-maboss`, `mcp-biomass`, `mcp-physicell*`). `install.py` only
provisions what is under `skills/`, so these must already exist in your
workspace. Your organisation also needs custom skills and custom agents enabled;
if they are off, `install()` returns errors saying so and there is no workaround
from inside the session.

The bundle must end up **in your Claude Science workspace** — the directory the
`python` / `bash` / `repl` tools share. Opening a download on your laptop is not
enough. Pick whichever route matches how you received it.

### Route A — clone the repo (recommended)

In the **`bash`** tool:

```bash
git clone https://github.com/marcorusc/claude-science-biomodelling.git
```

### Route B — from a file attached in chat

An attached file becomes an artifact, not a workspace file. In the **`python`**
tool:

```python
import tarfile
vid = host.artifacts(filename="claude-science-biomodelling.tar.gz",
                     exact=True)["artifacts"][0]["latest_version_id"]
tarfile.open(host.artifact_path(vid)).extractall(".")
```

### Then, in the `repl` tool

```python
exec(open("claude-science-biomodelling/install.py").read())
install(host)
```

`install()` auto-detects the bundle directory, so the clone folder may be named
anything; pass `root="path/to/dir"` to be explicit.

Check the result: `skills` and `profiles` list what was installed, `skipped` names
profiles whose connector is missing, and `errors` carries anything that failed.
Re-running is safe — existing profiles are updated in place and existing skill
files are replaced rather than duplicated.

It publishes the six skills and creates (or updates) the four profiles with their
connector and tool exclusions. Re-running is safe: existing profiles are updated
in place and skills are republished with `overwrite=True`.

## Using them

Select a profile from the session config popover, or dispatch from a lead agent:

```python
exec(host.skills.read("biomodelling-pipeline", "pipeline.py")["content"])
result = run_pipeline(host, SPEC)
```

The chain is sequential — curation, then dynamics, then configuration — with a
content-addressed handoff bundle saved as an artifact between hops. Fan-out belongs
*within* a stage, not across them. Exports are gated: the sign-off sentence only
reaches a specialist's task when `SPEC["approvals"]` supplies one.

## Caveats

- Written against `mcp-biomodelling-servers` 2.5.2 / `nekomata` 1.10.3. The skills
  name their version; recheck after a server upgrade.
- `biomodelling-handoff` documents live server bugs (unreadable simulation tables,
  placeholder figure bytes, overwrite refusals). Some will disappear with later
  releases — that file is the one to revise.
- The profiles assume connectors named exactly `neko`, `maboss`, `biomass`,
  `physicell`. Edit the `connector:` line in `agents/*.md` if yours differ.

## Relationship to the Claude Code version

These profiles are ports of the Claude Code specialists in
`marcorusc/agentic_system_for_modelling` (`.claude/agents/`, `.claude/skills/`).
That repo stays Claude Code's; this one is the Claude Science equivalent. The
behavioural contracts are the same — authority boundary, declared inference
policies, gated exports, state-ID discipline — while the Claude Code frontmatter
(hooks, `maxTurns`, `permissionMode`, `mcp__<server>__*` names) and the guarded
`runs/<agent>/report.md` output paths do not carry over; tool denials become
connector `exclude_tools_pattern`s instead.
