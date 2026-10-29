---
name: biomass-authoring
description: "Authoring guide for BioMASS ODE models through the biomass MCP connector (mcp-biomodelling-servers 2.5.1): Text2Model reaction syntax, choosing kinetics from a signalling network, the inspect/preview/apply editing cycle, replacement semantics, and tested authoring examples for NeKo-derived and standalone documents. Load before writing or editing reactions."
---

# BioMASS ODE authoring

Operational guide for the `biomass` MCP connector. Unlike `neko.*` and `maboss.*`,
these tools return structured dicts — `r["session_id"]` works.

Cross-server transport (importing a NeKo handoff), session volatility and the
bundle format are covered by `biomodelling-handoff`; load it before any import.

## Where to look

| Task | Reference |
|---|---|
| Reaction line grammar, values, fixed species, custom kinetics, observables | `references/reaction_syntax.md` |
| Turning a referenced network into reactions; choosing a representation and kinetic law | `references/network_to_reactions.md` |
| Inspect → preview → apply cycle, construction templates, editing existing files | `references/model_editing.md` |
| Worked NeKo-derived and standalone documents with line provenance | `references/authoring_examples.md` |

## Order of work

1. `create_session()` — one session per independent model; pass the full id explicitly.
2. Load the input: `import_neko_handoff(handoff_bundle=...)` for a network-derived
   model, or `import_text` / `import_text_file` for a standalone Text2Model document.
3. `inspect_reactions()` before any edit — note exact reaction IDs, generated
   symbols and the document version.
4. `build_reactions(expected_version=...)` with a preview before applying the same
   batch. `configure_model()` for numerical settings.
5. `validate_model()`, then `generate_model()` for an immutable revision;
   `inspect_model()` to read its equations and the origin of every quantity.
6. `run_simulation()` only for approved scenarios with explicit time spans.
7. `export_model_bundle()` preserves a server-side candidate — preservation is not
   approval.

## Replacement semantics — the main source of lost work

These three tools replace rather than patch:

- `set_reactions` replaces **all** reaction records and clears numerical configuration.
- `import_text` replaces the document and its line evidence.
- `configure_model` replaces the **entire** configuration.

After any of them, inspect the model and reapply the approved compatible settings.
Prefer `build_reactions` with `expected_version` for incremental work.

## Evidence rules

- A signed edge or a PMID does not establish a reaction or a kinetic law.
- Never infer units, and never treat a generated numerical default as evidence.
- Preserve many-to-many edge-to-reaction mappings and report unresolved coverage —
  never add dummy reactions to make coverage look complete.
- Keep `allow_placeholders=false` unless the exact hypothetical values were approved.
- A reaction the server marks `assumed` stays proposed until someone accepts it.

## Validate the four things separately

Syntax, generation, coverage and scientific criteria are distinct checks; report
them separately rather than as one pass/fail. Species projection graphs
(`export_model_graph`, `visualize_model`) do not encode signed mechanisms — do not
read regulation off them.
