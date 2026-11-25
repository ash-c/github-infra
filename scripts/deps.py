#!/usr/bin/env python3
"""Deterministic dependency maintenance for the weekly automation.

    scripts/deps.py report                       advisories + outdated dependencies (no changes)
    scripts/deps.py security                     bump dependencies with an advisory to the newest
                                                 release in their current major
    scripts/deps.py update [--exclude a,b]       bump everything to the newest release in its major
    scripts/deps.py check                        terraform fmt -check and validate (as CI)
    scripts/deps.py plan-status <pr-number>      read the CI plan comment; exit 1 unless "No changes."

Dependencies: provider constraints in versions.tf plus .terraform.lock.hcl, the Terraform CLI
(TF_VERSION in the workflows) and GitHub Actions pinned by commit SHA with a "# vX.Y.Z" comment.
A 0.x minor bump counts as a major, as do all majors; the script never applies one.
Add --json for machine-readable output. GitHub calls use GH_TOKEN/GITHUB_TOKEN or `gh auth token`.
"""
import argparse
import glob
import json
import os
import re
import subprocess
import sys
import urllib.request
from functools import lru_cache

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKFLOWS = os.path.join(ROOT, ".github", "workflows")
REPO = "ash-c/github-infra"
SEVERITIES = ["critical", "high", "medium", "low"]
ACTION_RE = re.compile(r"uses:\s*([\w.-]+/[\w.-]+)((?:/[\w./-]+)?)@([0-9a-f]{40})\s*#\s*(v?\d+\.\d+\.\d+)")
TF_VERSION_RE = re.compile(r"(TF_VERSION:\s*)(\d+\.\d+\.\d+)")
PROVIDER_RE = re.compile(r'(\w+)\s*=\s*\{\s*source\s*=\s*"([^"]+)"\s*version\s*=\s*"([^"]+)"\s*\}', re.S)
LOCK_RE = re.compile(r'provider "registry\.terraform\.io/([^"]+)" \{\s*version\s*=\s*"([^"]+)"(.*?)\n\}', re.S)


# ---------------------------------------------------------------- versions

def parse(v):
    m = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", v.strip())
    return tuple(int(x) for x in m.groups()) if m else None


def same_line(a, b):
    return a[0] == b[0] and (a[0] != 0 or a[1] == b[1])


def classify(old, new):
    a, b = parse(old), parse(new)
    if not same_line(a, b):
        return "major"
    return "patch" if a[1] == b[1] else "minor"


def targets(current, versions):
    """Newest release in the current major, and the newest release overall if it is a major."""
    cur = parse(current)
    stable = sorted({parse(v) for v in versions if parse(v)})
    newer = [v for v in stable if v > cur]
    in_line = [v for v in newer if same_line(v, cur)]
    beyond = [v for v in newer if not same_line(v, cur)]
    fmt = lambda t: ".".join(map(str, t)) if t else None
    return fmt(in_line[-1] if in_line else None), fmt(beyond[-1] if beyond else None)


def in_range(version, spec):
    """Evaluate a GitHub advisory range such as ">= 1.0.8, < 1.5.7"."""
    v = parse(version)
    for part in spec.split(","):
        m = re.fullmatch(r"\s*(>=|<=|>|<|=)?\s*(v?\d+\.\d+\.\d+)\s*", part)
        if not m:
            return True  # unknown syntax: report rather than miss it
        op, bound = m.group(1) or "=", parse(m.group(2))
        ok = {"<": v < bound, "<=": v <= bound, ">": v > bound, ">=": v >= bound, "=": v == bound}[op]
        if not ok:
            return False
    return True


# ---------------------------------------------------------------- HTTP

@lru_cache(maxsize=None)
def github_token():
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        return token
    try:
        return subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


@lru_cache(maxsize=None)
def get_json(url):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "github-infra-deps"}
    if url.startswith("https://api.github.com/") and github_token():
        headers["Authorization"] = f"Bearer {github_token()}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as res:
        return json.load(res)


def gh(path):
    return get_json(f"https://api.github.com{path}")


def github_releases(repo):
    tags = []
    for page in range(1, 4):
        batch = gh(f"/repos/{repo}/releases?per_page=100&page={page}")
        tags += [r["tag_name"] for r in batch if not r["draft"] and not r["prerelease"]]
        if len(batch) < 100:
            break
    return tags


def advisories_for(ecosystem, packages, version):
    found = {}
    for package in packages:
        for adv in gh(f"/advisories?ecosystem={ecosystem}&affects={package}&per_page=100"):
            for vuln in adv["vulnerabilities"]:
                if vuln["package"]["name"] != package or not in_range(version, vuln["vulnerable_version_range"] or ""):
                    continue
                patched = vuln.get("first_patched_version")
                found[adv["ghsa_id"]] = {
                    "id": adv["ghsa_id"],
                    "cve": adv.get("cve_id"),
                    "severity": adv["severity"],
                    "summary": adv["summary"],
                    "patched": patched,
                    "fixable": bool(patched and parse(patched) and same_line(parse(patched), parse(version))),
                }
    return list(found.values())


# ---------------------------------------------------------------- inventory

def read(path):
    with open(os.path.join(ROOT, path)) as f:
        return f.read()


def write(path, text):
    with open(os.path.join(ROOT, path), "w") as f:
        f.write(text)


def workflow_files():
    return sorted(os.path.relpath(p, ROOT) for p in glob.glob(os.path.join(WORKFLOWS, "*.y*ml")))


def lock_entries():
    return {
        src: {"version": ver, "h1": body.count('"h1:'),
              "constraints": (re.search(r'constraints\s*=\s*"([^"]*)"', body) or [None, ""])[1]}
        for src, ver, body in LOCK_RE.findall(read(".terraform.lock.hcl"))
    }


def inventory():
    deps = []
    locks = lock_entries()
    for name, source, constraint in PROVIDER_RE.findall(read("versions.tf")):
        ns, pname = source.split("/")
        current = locks[source]["version"]
        latest, major = targets(current, [v["version"] for v in get_json(
            f"https://registry.terraform.io/v1/providers/{source}/versions")["versions"]])
        module = f"github.com/{ns}/terraform-provider-{pname}"
        modules = [module] + ([f"{module}/v{parse(current)[0]}"] if parse(current)[0] >= 2 else [])
        deps.append({"kind": "provider", "name": source, "key": name, "constraint": constraint,
                     "current": current, "target": latest, "major": major,
                     "advisories": advisories_for("go", modules, current)})

    tf_versions = {m.group(2) for f in workflow_files() for m in TF_VERSION_RE.finditer(read(f))}
    for current in sorted(tf_versions):
        latest, major = targets(current, github_releases("hashicorp/terraform"))
        deps.append({"kind": "terraform", "name": "Terraform CLI", "current": current, "target": latest,
                     "major": major, "advisories": advisories_for("go", ["github.com/hashicorp/terraform"], current)})

    actions = {}
    for f in workflow_files():
        for repo, _sub, sha, tag in ACTION_RE.findall(read(f)):
            actions.setdefault((repo, tag.lstrip("v")), sha)
    for (repo, current), sha in sorted(actions.items()):
        latest, major = targets(current, github_releases(repo))
        deps.append({"kind": "action", "name": repo, "sha": sha, "current": current, "target": latest,
                     "major": major, "advisories": advisories_for("actions", [repo], current)})

    for d in deps:
        d["type"] = classify(d["current"], d["target"]) if d["target"] else None
    return deps


# ---------------------------------------------------------------- apply

def new_constraint(constraint, version):
    m = re.fullmatch(r"(\s*[~>=<!]*\s*)(\d+(?:\.\d+)*)\s*", constraint)
    if not m:
        raise SystemExit(f"Unsupported provider constraint: {constraint!r}")
    parts = len(m.group(2).split("."))
    return m.group(1) + ".".join(version.split(".")[:parts])


def resolve_sha(repo, tag):
    return gh(f"/repos/{repo}/commits/{tag}")["sha"]


def set_constraints(text, constraints):
    def sub(m):
        return m.group(1) + constraints.get(m.group(3), m.group(4)) + m.group(5)
    return re.sub(r'((\w+)\s*=\s*\{\s*source\s*=\s*"([^"]+)"\s*version\s*=\s*")([^"]+)(")', sub, text, flags=re.S)


def terraform_init(*flags):
    subprocess.run(["terraform", "init", *flags, "-input=false", "-no-color"], cwd=ROOT, check=True, stdout=sys.stderr,
                   env={**os.environ, "NETLIFY_API_TOKEN": os.environ.get("NETLIFY_API_TOKEN", "unused")})


def apply(deps):
    notes = []
    providers = [d for d in deps if d["kind"] == "provider"]
    if providers:
        before = lock_entries()
        wanted = {d["name"]: new_constraint(d["constraint"], d["target"]) for d in providers}
        final = set_constraints(read("versions.tf"), wanted)
        # init -upgrade reselects every provider, so hold the others at their locked version meanwhile.
        held = {src: f'= {e["version"]}' for src, e in before.items() if src not in wanted}
        write("versions.tf", set_constraints(final, held))
        try:
            terraform_init("-upgrade")
        finally:
            write("versions.tf", final)
        lock = read(".terraform.lock.hcl")
        for src in held:
            lock = re.sub(rf'(provider "registry\.terraform\.io/{re.escape(src)}" \{{.*?constraints\s*=\s*")[^"]*(")',
                          lambda m, c=before[src]["constraints"]: m.group(1) + c + m.group(2), lock, count=1, flags=re.S)
        write(".terraform.lock.hcl", lock)
        after = lock_entries()
        for d in providers:
            got = after[d["name"]]
            if got["version"] != d["target"]:
                notes.append(f'`{d["name"]}`: lockfile has {got["version"]}, expected {d["target"]}.')
            if got["h1"] != before[d["name"]]["h1"]:
                notes.append(f'`{d["name"]}`: h1 hash count changed {before[d["name"]]["h1"]} → {got["h1"]}; '
                             "check the lockfile still covers the same platforms.")

    for d in deps:
        if d["kind"] == "terraform":
            for f in workflow_files():
                write(f, TF_VERSION_RE.sub(lambda m: m.group(1) + d["target"] if m.group(2) == d["current"] else m.group(0), read(f)))
            notes.append("`TF_VERSION` changed: update the pinned Terraform version in this repo's Devin "
                         "environment blueprint (`initialize`) by hand to match.")
        elif d["kind"] == "action":
            tag = f'v{d["target"]}'
            sha = resolve_sha(d["name"], tag)
            pattern = re.compile(rf'({re.escape(d["name"])}(?:/[\w./-]+)?@){d["sha"]}(\s*#\s*)v?{re.escape(d["current"])}\b')
            for f in workflow_files():
                write(f, pattern.sub(lambda m: f"{m.group(1)}{sha}{m.group(2)}{tag}", read(f)))
            d["new_sha"] = sha
    return notes


# ---------------------------------------------------------------- output

def table(headers, rows):
    if not rows:
        return "_None._\n"
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(lines) + "\n"


def label(d):
    return d["name"] if d["kind"] == "terraform" else f'`{d["name"]}`'


def advisory_rows(deps):
    rows = []
    for d in deps:
        for a in sorted(d["advisories"], key=lambda a: SEVERITIES.index(a["severity"]) if a["severity"] in SEVERITIES else 9):
            fix = a["patched"] or "none"
            if a["patched"] and not a["fixable"]:
                fix += " (major)"
            rows.append([label(d), a["severity"], f'[{a["id"]}](https://github.com/advisories/{a["id"]})',
                         a["cve"] or "-", d["current"], fix])
    return rows


def severity_counts(deps):
    counts = {}
    for d in deps:
        for a in d["advisories"]:
            counts[a["severity"]] = counts.get(a["severity"], 0) + 1
    return ", ".join(f"{counts[s]} {s}" for s in SEVERITIES if s in counts) or "none"


ADVISORY_HEADERS = ["Dependency", "Severity", "Advisory", "CVE", "In use", "Patched in"]


def update_table(deps):
    return table(["Dependency", "From", "To", "Type"], [[label(d), d["current"], d["target"], d["type"]] for d in deps])


def major_table(deps):
    return table(["Dependency", "Current", "Latest", "Key breaking changes", "Estimated effort"],
                 [[label(d), d["current"], d["major"], "TODO", "TODO"] for d in deps if d["major"]])


def emit(args, data, markdown):
    print(json.dumps(data, indent=2) if args.json else markdown)


# ---------------------------------------------------------------- commands

def cmd_report(args):
    deps = inventory()
    updates = [d for d in deps if d["target"]]
    fixable = [d for d in deps if any(a["fixable"] for a in d["advisories"])]
    emit(args, {"dependencies": deps, "work": bool(updates or fixable)}, "\n".join([
        f"## Advisories ({severity_counts(deps)})", table(ADVISORY_HEADERS, advisory_rows(deps)),
        "## Patch and minor updates", update_table(updates),
        "## Major updates available", major_table(deps),
    ]))


def cmd_security(args):
    deps = inventory()
    chosen = [d for d in deps if d["target"] and any(a["fixable"] for a in d["advisories"])]
    for d in chosen:
        patched = max((a["patched"] for a in d["advisories"] if a["fixable"]), key=parse)
        if parse(d["target"]) < parse(patched):
            raise SystemExit(f'{d["name"]}: newest in-major release {d["target"]} is older than patched {patched}')
    notes = apply(chosen) if chosen else []
    fixed = [{**d, "advisories": [a for a in d["advisories"] if a["fixable"]]} for d in chosen]
    rest = [{**d, "advisories": [a for a in d["advisories"] if d not in chosen or not a["fixable"]]} for d in deps]
    rest = [d for d in rest if d["advisories"]]
    emit(args, {"fixed": fixed, "not_fixed": rest, "notes": notes}, "\n".join([
        f"## Advisories fixed ({severity_counts(fixed)})", table(ADVISORY_HEADERS, advisory_rows(fixed)),
        "## Updates applied", update_table(chosen),
        f"## Advisories not fixed ({severity_counts(rest)})", table(ADVISORY_HEADERS, advisory_rows(rest)),
        *(["## Notes", "\n".join(f"- {n}" for n in notes) + "\n"] if notes else []),
    ]))


def cmd_update(args):
    exclude = set(filter(None, (args.exclude or "").split(",")))
    deps = inventory()
    chosen = [d for d in deps if d["target"] and d["name"] not in exclude]
    left = [d for d in deps if d["target"] and d["name"] in exclude]
    notes = apply(chosen) if chosen else []
    emit(args, {"applied": chosen, "excluded": left, "notes": notes}, "\n".join([
        "## Patch and minor updates", update_table(chosen),
        *(["## Left out", "\n".join(f'- {label(d)} {d["current"]} → {d["target"]}: TODO reason' for d in left) + "\n"] if left else []),
        "## Major updates available", major_table(deps),
        *(["## Notes", "\n".join(f"- {n}" for n in notes) + "\n"] if notes else []),
    ]))


def cmd_check(_args):
    env = {**os.environ, "NETLIFY_API_TOKEN": os.environ.get("NETLIFY_API_TOKEN", "unused")}
    for cmd in (["terraform", "fmt", "-check", "-recursive", "-diff"],
                ["terraform", "init", "-input=false", "-no-color"],
                ["terraform", "validate", "-no-color"]):
        print("$ " + " ".join(cmd), flush=True)
        subprocess.run(cmd, cwd=ROOT, check=True, env=env)


def cmd_plan_status(args):
    pr = gh(f"/repos/{REPO}/pulls/{args.pr}")
    comments = gh(f"/repos/{REPO}/issues/{args.pr}/comments?per_page=100")
    plan = next((c for c in reversed(comments)
                 if c["user"]["login"] == "github-actions[bot]" and "<!-- terraform-plan -->" in c["body"]), None)
    if not plan:
        raise SystemExit(f"No Terraform plan comment on PR #{args.pr} yet.")
    m = re.search(r"\*\*(.+?)\*\* \(\[workflow run\]\(([^)]+)\), commit (\w+)\)", plan["body"])
    summary, run, commit = m.groups() if m else ("unknown", "", "")
    current = pr["head"]["sha"].startswith(commit) if commit else False
    no_changes = summary.startswith("No changes.")
    emit(args, {"summary": summary, "run": run, "commit": commit, "current": current, "no_changes": no_changes},
         f"{summary}\nCommit {commit} ({'current head' if current else 'NOT the current head: wait for CI'}), {run}")
    sys.exit(0 if no_changes and current else 1)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--json", action="store_true")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("report").set_defaults(fn=cmd_report)
    sub.add_parser("security").set_defaults(fn=cmd_security)
    u = sub.add_parser("update")
    u.add_argument("--exclude", help="comma-separated dependency names to leave out")
    u.set_defaults(fn=cmd_update)
    sub.add_parser("check").set_defaults(fn=cmd_check)
    s = sub.add_parser("plan-status")
    s.add_argument("pr", type=int)
    s.set_defaults(fn=cmd_plan_status)
    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
