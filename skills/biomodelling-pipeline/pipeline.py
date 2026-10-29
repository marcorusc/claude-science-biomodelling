"""Lead-side dispatch harness for the NeKo -> MaBoSS -> PhysiCell specialists.

Run in the `repl` kernel (that is where `host.delegate` lives):
    exec(open("biomodelling_pipeline.py").read())
    result = run_pipeline(host, SPEC)

Gating is structural: a stage's export sentence is written into the task ONLY if
spec["approvals"] carries a sign-off string for that stage. With no approvals the
pipeline runs curation and stops with the handoff pending, which is the intended
default.

spec keys: objective, genes, policies{path_policy,reuse_policy,max_len,only_signed,
consensus}, outputs (the ONE output-node set threaded through every stage),
authorised_mutations, approvals{topology,dynamics}, dynamics{mutations,
target_cell_type,initial_state}, configuration{domain,substrates,cell_types,rules,
links}, context_summary.
"""

# --------------------------------------------------------------------------- #
# Output schemas - one per stage. These restore the structured envelope.
# --------------------------------------------------------------------------- #

_POLICY = {"type": "object", "properties": {
    "path_policy": {"type": "string"}, "reuse_policy": {"type": "string"},
    "max_len": {"type": "integer"}, "only_signed": {"type": "boolean"},
    "consensus": {"type": "boolean"}},
    "required": ["path_policy", "reuse_policy", "max_len", "only_signed", "consensus"]}

CURATION_SCHEMA = {
  "type": "object",
  "required": ["status", "session_id", "network_id", "state_id", "dimensions",
               "inference_policy", "topology_changes", "flagged_recommendations",
               "literature_queue", "export", "decisions_required"],
  "properties": {
    "status": {"enum": ["complete", "needs_approval", "blocked"]},
    "session_id": {"type": "string"},
    "network_id": {"type": "string"},
    "state_id": {"type": "integer"},
    "dimensions": {"type": "object", "properties": {
        "nodes": {"type": "integer"}, "edges": {"type": "integer"},
        "components": {"type": "integer"}, "isolated_nodes": {"type": "integer"}},
        "required": ["nodes", "edges", "components", "isolated_nodes"]},
    "inference_policy": _POLICY,
    "topology_changes": {"type": "array", "items": {"type": "object", "properties": {
        "operation": {"type": "string"}, "affected": {"type": "string"},
        "under_instruction": {"type": "string"},
        "state_id_before": {"type": "integer"}, "state_id_after": {"type": "integer"}},
        "required": ["operation", "affected", "under_instruction",
                     "state_id_before", "state_id_after"]}},
    "flagged_recommendations": {"type": "array", "items": {"type": "object", "properties": {
        "recommendation": {"type": "string"}, "affected": {"type": "string"},
        "consequence_if_applied": {"type": "string"},
        "consequence_if_not": {"type": "string"}},
        "required": ["recommendation", "affected", "consequence_if_applied",
                     "consequence_if_not"]}},
    "literature_queue": {"type": "array", "items": {"type": "object", "properties": {
        "edge": {"type": "string"}, "current_effect": {"type": "string"},
        "why": {"type": "string"}}, "required": ["edge", "current_effect", "why"]}},
    "export": {"type": "object", "properties": {
        "sif_path": {"type": ["string", "null"]},
        "bnet_exported": {"type": "boolean"},
        "handoff_bundle_artifact": {"type": ["string", "null"],
            "description": "Artifact VERSION id of the saved bundle JSON, or null if not authorised."},
        "authorised_by": {"type": ["string", "null"]}},
        "required": ["sif_path", "bnet_exported", "handoff_bundle_artifact", "authorised_by"]},
    "decisions_required": {"type": "array", "items": {"type": "string"}},
    "warnings": {"type": "array", "items": {"type": "string"}}}}

DYNAMICS_SCHEMA = {
  "type": "object",
  "required": ["status", "session_id", "imported_from", "model_revision",
               "output_nodes", "runs", "export", "recommendation", "decisions_required"],
  "properties": {
    "status": {"enum": ["complete", "needs_approval", "blocked"]},
    "session_id": {"type": "string"},
    "imported_from": {"type": "object", "properties": {
        "neko_session_id": {"type": ["string", "null"]},
        "bundle_artifact": {"type": ["string", "null"]}},
        "required": ["neko_session_id", "bundle_artifact"]},
    "model_revision": {"type": ["string", "integer", "null"]},
    "output_nodes": {"type": "array", "items": {"type": "object", "properties": {
        "node": {"type": "string"}, "why": {"type": "string"}},
        "required": ["node", "why"]}},
    "parameters": {"type": "object"},
    "initial_state": {"type": "object"},
    "runs": {"type": "array", "items": {"type": "object", "properties": {
        "run_id": {"type": "string"}, "scenario": {"type": "string"},
        "mutation": {"type": ["string", "null"]}, "summary": {"type": "string"},
        "matched_parameters": {"type": "boolean"}},
        "required": ["run_id", "scenario", "mutation", "summary", "matched_parameters"]}},
    "rule_changes": {"type": "array", "items": {"type": "object", "properties": {
        "node": {"type": "string"}, "before": {"type": "string"},
        "after": {"type": "string"},
        "provenance": {"enum": ["fitted-for-dynamics", "literature-derived"]},
        "under_instruction": {"type": "string"}},
        "required": ["node", "before", "after", "provenance", "under_instruction"]}},
    "stability_warnings": {"type": "array", "items": {"type": "string"}},
    "export": {"type": "object", "properties": {
        "handoff_bundle_artifact": {"type": ["string", "null"]},
        "target_cell_type": {"type": ["string", "null"]},
        "authorised_by": {"type": ["string", "null"]}},
        "required": ["handoff_bundle_artifact", "target_cell_type", "authorised_by"]},
    "recommendation": {"enum": ["proceed_to_configuration", "test_more_mutations",
                                "rule_refinement", "return_to_curation"]},
    "decisions_required": {"type": "array", "items": {"type": "string"}}}}

CONFIG_SCHEMA = {
  "type": "object",
  "required": ["status", "session_id", "imported", "domain", "substrates",
               "cell_types", "rules", "physiboss", "artifacts",
               "unresolved_assumptions", "decisions_required"],
  "properties": {
    "status": {"enum": ["complete", "needs_approval", "blocked"]},
    "session_id": {"type": "string"},
    "imported": {"type": "object", "properties": {
        "maboss_model_revision": {"type": ["string", "integer", "null"]},
        "bundle_artifact": {"type": ["string", "null"]},
        "lineage": {"type": ["string", "null"]}},
        "required": ["maboss_model_revision", "bundle_artifact", "lineage"]},
    "domain": {"type": "object"},
    "substrates": {"type": "array", "items": {"type": "object", "properties": {
        "name": {"type": "string"}, "units": {"type": "string"},
        "origin": {"type": "string"}}, "required": ["name", "units", "origin"]}},
    "cell_types": {"type": "array", "items": {"type": "string"}},
    "rules": {"type": "array", "items": {"type": "object", "properties": {
        "signal": {"type": "string"}, "behaviour": {"type": "string"},
        "node": {"type": ["string", "null"]}, "hypothesis": {"type": "string"}},
        "required": ["signal", "behaviour", "node", "hypothesis"]}},
    "physiboss": {"type": "object"},
    "artifacts": {"type": "object", "properties": {
        "xml_path": {"type": ["string", "null"]},
        "cell_rules_csv_path": {"type": ["string", "null"]},
        "bundle_path": {"type": ["string", "null"]}},
        "required": ["xml_path", "cell_rules_csv_path", "bundle_path"]},
    "unresolved_assumptions": {"type": "array", "items": {"type": "string"}},
    "warnings": {"type": "array", "items": {"type": "string"}},
    "decisions_required": {"type": "array", "items": {"type": "string"}}}}

SCHEMAS = {"curation": CURATION_SCHEMA, "dynamics": DYNAMICS_SCHEMA,
           "configuration": CONFIG_SCHEMA}

# --------------------------------------------------------------------------- #
# Task builders - the "bounded invocation". A child sees ONLY this text.
# --------------------------------------------------------------------------- #

_SAVE = ("Save the bundle with json.dump to a .json file in your workspace, call "
         "save_artifacts on it, and return the artifact VERSION id in "
         "export.handoff_bundle_artifact. Never return a server path as the handoff.")

def curation_task(spec):
    p = spec["policies"]
    t = [f"Objective: {spec['objective']}",
         "",
         f"Build a NeKo network from these seed genes: {', '.join(spec['genes'])}.",
         f"Use exactly these inference policies and report the effective values: "
         f"path_policy={p['path_policy']}, reuse_policy={p['reuse_policy']}, "
         f"max_len={p['max_len']}, only_signed={p['only_signed']}, "
         f"consensus={p['consensus']}.",
         "",
         "Audit the result: analyze_connectivity, list the components and any "
         "isolated nodes, and build the edge-level literature-evidence queue.",
         "Export SIF as a working artifact.",
         "",
         "Declare EXACTLY these output nodes on export_neko_handoff(output_nodes=[...]): "
         + ", ".join(spec["outputs"]) + ". This set is the contract for the whole "
         "pipeline: PhysiCell rejects a downstream handoff whose declared outputs "
         "cannot be reconciled with the NeKo core, so do not declare a different set."]
    muts = spec.get("authorised_mutations")
    if muts:
        t += ["", "AUTHORISED topology mutations for this task (do no others): " + muts]
    else:
        t += ["", "No topology mutation is authorised in this task. If the network "
                  "needs repair, report it as a flagged recommendation and stop there."]
    ok = spec.get("approvals", {}).get("topology")
    if ok:
        t += ["", f"TOPOLOGY SIGN-OFF: {ok}",
              "The topology and its literature review have been reviewed and approved. "
              "Produce the NeKo-to-MaBoSS handoff and pack it with export_handoff_bundle. "
              + _SAVE]
    else:
        t += ["", "BNET export and the typed handoff are NOT authorised in this task. "
                  "Finish the curation work and report the handoff as pending sign-off; "
                  "set export.handoff_bundle_artifact to null."]
    return "\n".join(t)

def dynamics_task(spec, bundle_vid):
    d = spec["dynamics"]
    t = [f"Objective: {spec['objective']}",
         "",
         f"Import the NeKo handoff bundle at {{{{artifact:{bundle_vid}}}}} - load the "
         "JSON and pass it to import_neko_handoff(handoff_bundle=...). Report the "
         "upstream NeKo session id from the lineage.",
         "",
         "Do NOT call build_simulation after import_neko_handoff: the import already "
         "attaches a loaded model, and build_simulation looks for an output.bnd that "
         "only the bnet_to_bnd_and_cfg route writes, so it fails with ENOENT and costs "
         "you a re-import. Note also that MCP tool failures come back as a STRING "
         "beginning 'Error executing tool' rather than raising - check for that prefix.",
         "",
         f"Output nodes to select (and only these): {', '.join(spec['outputs'])}. "
         "This is the set the upstream NeKo manifest declares; keep it identical. If "
         "an extra observable is needed, add it as a declared readout rather than "
         "swapping the output set, or the PhysiCell import will reject the handoff.",
         f"Initial state / parameter instructions: {d.get('initial_state', 'server defaults; state them explicitly in the report')}.",
         "",
         "Run wild type, then each of these mutation scenarios under MATCHED "
         "parameters, recording run_id and model_revision for every run:"]
    for m in d.get("mutations", []):
        t.append(f"  - {m}")
    if not d.get("mutations"):
        t.append("  - (none requested: wild type only)")
    t += ["", "Do NOT change any logical rule. Rule refinement is not invoked in this task."]
    ok = spec.get("approvals", {}).get("dynamics")
    if ok:
        t += ["", f"RESULTS SIGN-OFF: {ok}",
              "WT and mutation results have been reviewed and approved. Export the "
              f"MaBoSS-to-PhysiCell handoff with target_cell_type='{d['target_cell_type']}' "
              "and pack it with export_handoff_bundle. " + _SAVE]
    else:
        t += ["", "The PhysiCell handoff is NOT authorised in this task. Report it as "
                  "pending sign-off and set export.handoff_bundle_artifact to null."]
    return "\n".join(t)

def config_task(spec, bundle_vid):
    c = spec["configuration"]
    t = [f"Objective: {spec['objective']}",
         "",
         f"Import the MaBoSS handoff bundle at {{{{artifact:{bundle_vid}}}}} with "
         "import_maboss_handoff(handoff_bundle=...). Report the imported model "
         "revision and the lineage string.",
         "",
         f"Domain: {c['domain']}",
         f"Substrates (name, units, value, origin): {c['substrates']}",
         f"Cell types: {c['cell_types']}",
         f"Signal-behaviour rules to configure as explicit hypotheses: {c.get('rules', 'none')}",
         f"PhysiBoSS input/output links: {c.get('links', 'none')}",
         "",
         "Discover exact signal and behaviour names before writing any rule. Never "
         "invent a unit or a parameter: if a value is not given above, ask rather "
         "than choose one. Report the STORED values each tool returns.",
         "Export the Cell Rules CSV before the XML when rules exist.",
         "You configure only - do not attempt to run PhysiCell."]
    return "\n".join(t)

TASKS = {"curation": curation_task, "dynamics": dynamics_task,
         "configuration": config_task}

# --------------------------------------------------------------------------- #
# Audit - read this before believing any number a child returned.
# --------------------------------------------------------------------------- #

def audit(stage, result, spec):
    """Return a list of problems. Empty list == safe to continue."""
    problems = []
    if result.get("status") == "running":
        return [f"{stage}: still running (frame {result.get('frame_id')})"]
    if result.get("error"):
        return [f"{stage}: failed - {result['error']}"]
    dev = result.get("deviations") or []
    if dev and dev != ["none"]:
        problems.append(f"{stage}: declared deviations {dev} - these travel with every "
                        "number below; do not report counts from capped input as findings")
    if isinstance(dev, list) and dev and str(dev[0]).startswith("UNDECLARED"):
        problems.append(f"{stage}: UNDECLARED deviations - coverage unknown")
    so = result.get("structured_output") or {}
    if not so:
        return problems + [f"{stage}: no structured output returned"]
    if so.get("status") != "complete":
        problems.append(f"{stage}: status={so.get('status')}")
    for d in so.get("decisions_required", []):
        problems.append(f"{stage}: decision required - {d}")
    if stage == "dynamics":
        got_out = sorted(x.get("node") for x in so.get("output_nodes", []))
        want = sorted(spec["outputs"])
        if got_out and got_out != want:
            problems.append(
                f"{stage}: output-node drift - declared upstream {want}, selected "
                f"{got_out}; PhysiCell will refuse this handoff")
    exp = so.get("export", {})
    approved = bool(spec.get("approvals", {}).get(
        {"curation": "topology", "dynamics": "dynamics"}.get(stage, "")))
    got = exp.get("handoff_bundle_artifact")
    if got and not approved:
        problems.append(f"{stage}: GATE VIOLATION - exported a handoff without sign-off")
    if approved and not got:
        problems.append(f"{stage}: sign-off given but no handoff bundle artifact returned")
    return problems

# --------------------------------------------------------------------------- #
# Pipeline
# --------------------------------------------------------------------------- #

_PROFILE = {"curation": "NETWORK_CURATOR",
            "dynamics": "BOOLEAN_DYNAMICS_MODELER",
            "configuration": "MULTICELLULAR_CONFIGURATOR"}
_NAME = {"curation": "Curation", "dynamics": "Dynamics", "configuration": "Configuration"}

def run_stage(host, stage, spec, bundle_vid=None, timeout=None):
    task = TASKS[stage](spec) if stage == "curation" else TASKS[stage](spec, bundle_vid)
    # host.delegate rejects a request dict PLUS keyword options - everything
    # (output_schema included) goes inside the dict.
    req = {"task": task, "name": _NAME[stage], "profile": _PROFILE[stage],
           "output_schema": SCHEMAS[stage]}
    if spec.get("context_summary"):
        req["context_summary"] = spec["context_summary"]
    if timeout:
        req["timeout"] = timeout
    return host.delegate(req)

def run_pipeline(host, spec, stop_after=None, timeout=None):
    """Run curation -> dynamics -> configuration, stopping at the first gate."""
    out = {"stages": {}, "problems": [], "stopped_at": None}
    vid = None
    for stage in ("curation", "dynamics", "configuration"):
        r = run_stage(host, stage, spec, bundle_vid=vid, timeout=timeout)
        out["stages"][stage] = r
        probs = audit(stage, r, spec)
        out["problems"] += probs
        if probs:
            out["stopped_at"] = stage
            return out
        if stop_after == stage:
            out["stopped_at"] = stage
            return out
        if stage != "configuration":
            vid = (r.get("structured_output") or {}).get("export", {}).get(
                "handoff_bundle_artifact")
            if not vid:
                out["stopped_at"] = stage
                out["problems"].append(
                    f"{stage}: no handoff bundle - pipeline stops here, which is the "
                    "expected behaviour without a sign-off in spec['approvals']")
                return out
    return out
