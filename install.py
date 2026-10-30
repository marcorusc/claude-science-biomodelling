"""Install the biomodelling specialists into a Claude Science workspace.

Run in the `repl` tool, from the workspace holding the clone (the repo root is
auto-detected):

    exec(open("claude-science-biomodelling/install.py").read())
    install(host)                  # everything
    install(host, skills_only=True)
    install(host, profiles_only=True)

Source of truth is the repo itself: one markdown file per profile under
`agents/`, one directory per skill under `skills/`. Nothing is generated or
cached - edit the files and re-run.

Requires the MCP connector each profile names (neko, maboss, biomass,
physicell) to be attached to the account; install() skips a profile whose
connector is missing and reports it. Custom skills and custom agents must be
enabled for the organisation.
"""
import json, os


def find_root(start="."):
    """Locate the repo root: the directory holding agents/ and skills/."""
    def looks_right(d):
        return os.path.isdir(os.path.join(d, "agents")) and \
               os.path.isdir(os.path.join(d, "skills"))
    if looks_right(start):
        return start
    for d in sorted(os.listdir(start)):
        p = os.path.join(start, d)
        if os.path.isdir(p) and looks_right(p):
            return p
    raise FileNotFoundError(
        "No agents/ + skills/ pair found in '%s' or its immediate "
        "subdirectories - clone or extract the repo into the workspace first."
        % os.path.abspath(start))


def parse_agent(path):
    """Parse an agents/*.md profile definition.

    Frontmatter scalars are JSON-encoded where quoted, so a description
    containing ': ' is safe. The body after the frontmatter is the system
    prompt, verbatim.
    """
    text = open(path).read()
    if not text.startswith("---\n"):
        raise ValueError("%s: missing frontmatter" % path)
    _, fm, body = text.split("---\n", 2)
    out, skills, in_skills = {}, [], False
    for line in fm.splitlines():
        if not line.strip():
            continue
        if line.startswith("  - "):
            if not in_skills:
                raise ValueError("%s: list item outside 'skills:'" % path)
            skills.append(line[4:].strip())
            continue
        k, _, v = line.partition(":")
        k, v = k.strip(), v.strip()
        in_skills = (k == "skills")
        if in_skills:
            continue
        out[k] = json.loads(v) if v[:1] in '"[{' or v in ("null", "true", "false") else v
    for required in ("name", "display_name", "description", "connector"):
        if required not in out:
            raise ValueError("%s: frontmatter missing '%s'" % (path, required))
    out["skill_names"] = skills
    out["system_prompt"] = body.strip("\n")
    return out


def discover(root):
    """Return (skills, profiles) found in the repo."""
    sk_dir = os.path.join(root, "skills")
    skills = {}
    for s in sorted(os.listdir(sk_dir)):
        d = os.path.join(sk_dir, s)
        if not os.path.isdir(d):
            continue
        extra = []
        for base, _, files in os.walk(d):
            for f in sorted(files):
                rel = os.path.relpath(os.path.join(base, f), d)
                if rel != "SKILL.md":
                    extra.append(rel)
        skills[s] = sorted(extra)
    ag_dir = os.path.join(root, "agents")
    profiles = [parse_agent(os.path.join(ag_dir, f))
                for f in sorted(os.listdir(ag_dir)) if f.endswith(".md")]
    return skills, profiles


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


def install(host, root=None, skills_only=False, profiles_only=False, overwrite=True):
    root = root or find_root()
    skills, profiles = discover(root)
    done = {"root": root, "skills": [], "profiles": [], "skipped": [], "errors": []}

    if not profiles_only:
        for s, extra in skills.items():
            try:
                d = os.path.join(root, "skills", s)
                _write(host, s, "SKILL.md", open(os.path.join(d, "SKILL.md")).read())
                for f in extra:
                    _write(host, s, f, open(os.path.join(d, f)).read())
                host.skills.publish(s, overwrite=overwrite)
                done["skills"].append(s)
            except Exception as e:
                done["errors"].append("skill %s: %s" % (s, e))

    if not skills_only:
        have = {c["name"] for c in host.agents.list_connectors()}
        existing = {a["name"] for a in host.agents.list()}
        for p in profiles:
            if p["connector"] not in have:
                done["skipped"].append(
                    "%s (connector '%s' not attached)" % (p["name"], p["connector"]))
                continue
            try:
                if p["name"] in existing:
                    host.agents.update(p["name"], {
                        "display_name": p["display_name"],
                        "description": p["description"],
                        "system_prompt": p["system_prompt"],
                        "skill_names": p["skill_names"]})
                else:
                    host.agents.create(p["name"], p["display_name"], p["description"],
                                       system_prompt=p["system_prompt"],
                                       skill_names=p["skill_names"])
                host.agents.attach_connector(
                    p["name"], p["connector"],
                    exclude_tools_pattern=p.get("exclude_tools_pattern"))
                done["profiles"].append(p["name"])
            except Exception as e:
                done["errors"].append("profile %s: %s" % (p["name"], e))
    return done
