---
name: biomodelling-pipeline
description: "Lead-side dispatch harness for the NeKo -> MaBoSS -> PhysiCell specialist chain: per-stage output schemas, bounded-invocation task builders whose export sentences appear only when a sign-off is supplied, an audit that reads deviations and gate consistency, and a run_pipeline that stops at the first gate. Load when orchestrating NETWORK_CURATOR, BOOLEAN_DYNAMICS_MODELER and MULTICELLULAR_CONFIGURATOR as sub-agents."
---

# Dispatching the modelling specialists

Runs in the `repl` kernel, where `host.delegate` lives.

```python
exec(host.skills.read("biomodelling-pipeline", "pipeline.py")["content"])
result = run_pipeline(host, SPEC)
```

## The spec

```python
SPEC = {
  "objective": "one sentence; it is copied into every stage's task",
  "genes": ["TP53", "MDM2", "CDKN1A", "E2F1"],
  "policies": {"path_policy": "one_shortest", "reuse_policy": "discovered_paths",
               "max_len": 1, "only_signed": True, "consensus": True},
  "outputs": ["TP53", "E2F1"],          # ONE set, threaded through every stage
  "authorised_mutations": "text, or omit for none",
  "approvals": {},                       # {"topology": "...", "dynamics": "..."}
  "dynamics": {"mutations": ["TP53 knockout"], "target_cell_type": "tumor_cell"},
  "configuration": {"domain": "500x500x20 um, 2D", "substrates": "none",
                    "cell_types": "tumor_cell"},
  "context_summary": "optional background every child receives",
}
```

`spec["outputs"]` is the one that bites. PhysiCell reconciles the MaBoSS manifest
against its NeKo parent and refuses the import when the declared output sets differ,
so the harness declares the same set at curation and selects it at dynamics, and
`audit` fails the stage on drift.

## Gating is structural, not advisory

A stage's export instruction is written into the task **only** when
`spec["approvals"]` carries a sign-off string for that stage. With `approvals={}`
the curator does the curation work and reports the handoff as pending — there is no
wording in the task that would let it export. Put the real provenance in the string
(who approved what, when); it is echoed back in `export.authorised_by`.

`audit()` also flags the reverse: a bundle returned without a sign-off is a GATE
VIOLATION, not a convenience.

## Reading a result before believing it

`run_pipeline` stops at the first stage whose audit is non-empty and returns
everything collected so far. Audit catches: declared `deviations` other than
`["none"]`, `UNDECLARED` coverage, `status != complete`, any `decisions_required`,
output-node drift, and both directions of gate inconsistency.

Deviations are the important part. A child that could not read a result table, or
re-ran a scenario, says so there — and that limit travels with every number you
quote from it.

## Shape of the run

The chain is sequential; fan-out belongs *within* a stage (several mutation
scenarios, competing topologies), dispatched as a list to `host.delegate`. Each hop
hands the next a content-addressed bundle saved as a JSON artifact — never a server
path. See `biomodelling-handoff` for why, and for the server quirks that will
otherwise cost a child half its turns.

## Resuming

`run_pipeline` is a convenience over `run_stage`. After answering a stage's
`decisions_required`, resume from the bundle you already have:

```python
r2 = run_stage(host, "dynamics", SPEC, bundle_vid="<artifact version id>")
```

A follow-up to a child that already finished should go through
`host.send_message(frame_id, ...)` — it keeps its session ids and context — rather
than a fresh delegation.
