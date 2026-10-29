---
name: biomodelling-handoff
description: "How the neko, maboss, biomass and physicell MCP connectors pass models to each other in this deployment: content-addressed handoff bundles (the path-based route cannot work, each server has its own container), bimodal edges blocking BNET export, session volatility and artifact recovery, per-server return types, and handing a bundle to another agent as an artifact. Load before any cross-server export or handoff, or when an import fails with ENOENT."
---

# Cross-server handoff for the biomodelling MCP connectors

Verified against `mcp-biomodelling-servers` 2.5.2 (NeKo `nekomata` 1.10.3) as deployed
here, re-tested end to end after the 2.5.2 upgrade. Everything below
was reproduced in this workspace, not inferred from the docstrings. Recheck after a
server upgrade — several items are bugs that are expected to be fixed.

## The path-based handoff cannot work here

Each server (`neko`, `maboss`, `biomass`, `physicell`) runs in its own container
with a private root spelled with the **same** `$ORG/workspaces/` prefix as the agent
sandbox. A path one server reports is therefore syntactically valid in the caller's
namespace with nothing at the other end, and the import fails as a plain ENOENT —
it looks like a missing file, not an isolation boundary. No `_mcp-*` directory
exists in the sandbox at all.

Do not copy files between servers, do not hand a path from one server to another,
and do not treat `Errno 2` here as a sign the exporter failed.

## Use the bundle

`neko.export_handoff_bundle(manifest_path)` and `maboss.export_handoff_bundle(manifest_path)`
pack the manifest and every file it references into one JSON value:

```
{schema_name: "mcp-biomodelling-handoff-bundle", schema_version: "1.0",
 server, handoff_type, manifest_name, manifest_sha256,
 encoding: "gzip+base64", blobs}
```

`blobs` is keyed by the SHA-256 of the **uncompressed** bytes (content-addressed;
integrity was independently verified by decoding, gunzipping and re-hashing every
blob). Maximum 64 entries — a very large export can exceed it.

All three importers accept `handoff_bundle=` as an alternative to `manifest_path`:
`maboss.import_neko_handoff`, `biomass.import_neko_handoff`,
`physicell.import_maboss_handoff`.

### Verified chains

NeKo → MaBoSS → PhysiCell:

```
neko.create_network(list_of_initial_genes=[...])
neko.remove_bimodal_interactions()          # or edit_interactions — see below
neko.export_neko_handoff(biological_context=...)   # -> manifest path, in prose
neko.export_handoff_bundle(manifest_path)   # neko-to-maboss, 3 blobs
maboss.import_neko_handoff(handoff_bundle=...)
maboss.build_simulation() / run_simulation()
maboss.export_maboss_handoff()
maboss.export_handoff_bundle(manifest_path) # maboss-to-physicell, 7 blobs
physicell.import_maboss_handoff(handoff_bundle=...)
```

The PhysiCell import attaches the model to the target cell type and reports
`Lineage: NeKo session <id>`, so provenance survives all three hops.

NeKo → BioMASS: `export_biomass_handoff` → `export_handoff_bundle` →
`biomass.import_neko_handoff(handoff_bundle=...)`, which returns
`{server, session_id, document, coverage}`.

Because `export_handoff_bundle` reads files from **disk** rather than session memory,
a bundle can be produced after the exporting session has already been evicted.

## Getting the manifest path out

`export_neko_handoff` and `export_biomass_handoff` declare
`{server, session_id, manifest_file, manifest}` but actually return a prose string,
so `result["manifest_file"]` is empty. Scrape it:

```python
import re
path = re.search(r"(/[\w\-./]+\.handoff\.json)", str(result)).group(1)
```

`export_handoff_bundle` itself returns a proper structured dict.

## Return types differ per server

- `neko.*` and `maboss.*` — human-formatted prose. A session id must be regexed
  out, and the wording differs per server (`"Created session: <uuid>"` on NeKo,
  `"Session created: <uuid> (set as default)"` on MaBoSS), so match a bare UUID
  rather than the sentence.
- `biomass.*` — structured dicts; `r["session_id"]` works.
- Check the shape before indexing into it; do not assume the declared schema.

Note also that `neko.create_network` takes `list_of_initial_genes`, not `genes`.

## Bimodal edges block BNET export

`export_network(format="bnet")` and `export_neko_handoff` fail while any bimodal
edge (a pair recorded with both signs) remains: NeKo generates one BNET model per
sign assignment and the export requires exactly one. Since 2.5.2 the diagnostic is
precise and actionable — it reports how many remain, lists them by name
(`**Unresolved:** MDM2 -> TP53`), states that connectivity is *not* the cause, and
gives both remedies. Trust it; no separate `analyze_connectivity` run is needed to
interpret it.

Remedies, in the order the server itself recommends:
1. `edit_interactions` with `operation='set_effect'`, an `effect` of `stimulation`
   or `inhibition`, a `rationale` and `evidence` — keeps the edge and its
   references, and is a recorded curation decision.
2. `remove_bimodal_interactions()` — deletes every bimodal edge with its
   references, can disconnect the network, and needs an `analyze_connectivity()`
   afterwards. Report what was lost.

Resolving bimodals before `export_neko_handoff` is what makes the whole
NeKo → MaBoSS route work; with them resolved, BNET export succeeds.

## Required arguments on the exporters

`neko.export_neko_handoff` and `neko.export_biomass_handoff` both **require**
`biological_context` (a non-empty string: the question the network must stay
attached to). `maboss.export_maboss_handoff` **requires** `target_cell_type`, and
optionally takes `biological_context` and `simulation_summary`. The importers
(`maboss.import_neko_handoff`, `biomass.import_neko_handoff`,
`physicell.import_maboss_handoff`, `maboss.bnet_to_bnd_and_cfg`) have no required
arguments — supply `handoff_bundle=` explicitly.

## Loading a standalone BNET

`maboss.bnet_to_bnd_and_cfg(bnet_path=...)` resolves only inside the MaBoSS
container; a sandbox path fails with "BNET file not found". Pass the file's
**content** instead — `bnet_to_bnd_and_cfg(bnet_text="A, B\nB, !A\n")` — then
`build_simulation()`. Verified working.

## MCP failures arrive as text, not exceptions

A tool-level failure returns a plain string beginning `"Error executing tool
<name>: ..."` — `host.mcp` does **not** raise. A `try/except` around the call will
happily record a failure as a success. Check the prefix:

```python
r = host.mcp("maboss", "build_simulation", session_id=sid)
if str(r).startswith("Error executing tool"):
    ...  # handle it
```

## Output nodes are a whole-pipeline contract

`physicell.import_maboss_handoff` reconciles the MaBoSS manifest against its NeKo
parent and **refuses the attachment** when the declared output sets cannot be
reconciled (observed: NeKo parent declared `[CDKN1A, E2F1]`, MaBoSS declared
`[E2F1, TP53]` with an empty readouts block → import rejected, no model attached).
Decide the output set once, declare it on `export_neko_handoff(output_nodes=[...])`,
and select the same set in MaBoSS. An extra observable goes in as a declared
**readout**, not as a swap of the output set. The bundle cannot be patched after the
fact — blobs are content-addressed and the manifest hash is the provenance record,
so the fix is a re-export upstream.

## Other 2.5.2 edges worth knowing

- `export_maboss_handoff` refuses to overwrite an existing handoff in the session
  (`Refusing to overwrite existing MaBoSS handoff artifacts`). A corrected export
  needs a new name; both then exist server-side.
- `get_simulation_result` returns a prose header plus a server-side path, so the
  numeric state-probability table cannot be read back into the sandbox. The result
  CSV embedded in an exported handoff bundle is currently the only route by which a
  MaBoSS table reaches the caller.
- `visualize_network_trajectories` writes PNGs server-side, but the image bytes
  arrive through the connector as a placeholder — no figure artifact can be made
  from them.
- `physicell.list_loaded_components` returns only its header sentence in this build,
  so stored component values are unreadable. Do not substitute invented values.

## Sessions are volatile

NeKo and MaBoSS evict in-memory sessions quickly. Two consequences:

- Run a server's work in as few calls as possible, and always pass the **full**
  session id explicitly rather than relying on a default session.
- Recovery without re-querying OmniPath: `list_artifact_sessions()` to find the
  session's files on disk, then
  `create_network(sif_file=".../artifacts/NeKo/<session>/Network.sif")` rebuilds the
  exact network.

## Handing a bundle to another agent

A sub-agent runs in its own working directory and cannot read the parent's files by
path. Save the bundle as a JSON artifact and pass the artifact marker in the task
text; the child resolves the marker to a readable path in its own code.

```python
# producing agent
import json
json.dump(bundle, open("neko_to_maboss_bundle.json", "w"))
# save_artifacts(files=["neko_to_maboss_bundle.json"], language="python") -> version_id
```

Then the next agent's task says: *"Import the bundle at `{{artifact:VERSION_ID}}`
with `maboss.import_neko_handoff(handoff_bundle=...)`"*, and the child does
`json.load(open(path))` on the resolved marker. Keep the bundle as an artifact
rather than re-exporting it — it is the provenance record for that hop.
