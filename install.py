"""Install the biomodelling specialists into a Claude Science workspace.

Run in the `repl` tool, from the workspace holding the clone or the extracted
bundle (the root is auto-detected):

    exec(open("claude-science-biomodelling/install.py").read())
    install(host)                 # everything
    install(host, skills_only=True)
    install(host, profiles_only=True)

Requires the four MCP connectors `neko`, `maboss`, `biomass`, `physicell`
(mcp-biomodelling-servers 2.5.2) to be attached to the account. install()
reports any that are missing and skips the profile that needs them.
"""
import json, os

def find_root(start="."):
    """Locate the directory holding bundle.json: here, or one level down."""
    if os.path.isfile(os.path.join(start, "bundle.json")):
        return start
    for d in sorted(os.listdir(start)):
        p = os.path.join(start, d)
        if os.path.isdir(p) and os.path.isfile(os.path.join(p, "bundle.json")):
            return p
    raise FileNotFoundError(
        "bundle.json not found in '%s' or its immediate subdirectories - "
        "extract or clone the bundle into the workspace first." % os.path.abspath(start))

def _bundle(root):
    return json.load(open(os.path.join(root, "bundle.json")))

def _write(host, name, path, content):
    """Create the file, or replace it wholesale if the skill already has one.

    host.skills.edit refuses to create a path that exists, so a re-install has
    to go through the str_replace form with the current content as old_string.
    """
    try:
        host.skills.edit(name, path, content)
        return "created"
    except Exception as e:
        if "already exists" not in str(e):
            raise
        cur = host.skills.read(name, path)["content"]
        if cur == content:
            return "unchanged"
        host.skills.edit(name, path, content, old_string=cur)
        return "replaced"

def install(host, root=None, skills_only=False,
            profiles_only=False, overwrite=True):
    root = root or find_root()
    b = _bundle(root)
    done = {"skills": [], "profiles": [], "skipped": [], "errors": []}

    if not profiles_only:
        for s in b["skills"]:
            try:
                _write(host, s, "SKILL.md",
                       open(os.path.join(root, "skills", s, "SKILL.md")).read())
                for f in b["extra_files"].get(s, []):
                    _write(host, s, f, open(os.path.join(root, "skills", s, f)).read())
                host.skills.publish(s, overwrite=overwrite)
                done["skills"].append(s)
            except Exception as e:
                done["errors"].append(f"skill {s}: {e}")

    if not skills_only:
        have = {c["name"] for c in host.agents.list_connectors()}
        existing = {a["name"] for a in host.agents.list()}
        for p in b["profiles"]:
            if p["connector"] not in have:
                done["skipped"].append(f"{p['name']} (connector '{p['connector']}' not attached)")
                continue
            try:
                if p["name"] in existing:
                    host.agents.update(p["name"], {
                        "display_name": p["display_name"], "description": p["description"],
                        "system_prompt": p["system_prompt"], "skill_names": p["skill_names"]})
                else:
                    host.agents.create(p["name"], p["display_name"], p["description"],
                                       system_prompt=p["system_prompt"],
                                       skill_names=p["skill_names"])
                host.agents.attach_connector(p["name"], p["connector"],
                                             exclude_tools_pattern=p["exclude_tools_pattern"])
                done["profiles"].append(p["name"])
            except Exception as e:
                done["errors"].append(f"profile {p['name']}: {e}")
    return done
