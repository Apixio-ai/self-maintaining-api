#!/usr/bin/env python3
"""
Self-Maintaining APIs - demo maintainer v2 (PR-first, never auto-merges).

Upgrades over v1:
  * REAL vendor change, not simulated. The spec change below is Stripe's
    documented Billing Meter Usage change, API version 2025-09-30.preview:
    https://docs.stripe.com/changelog/clover/2025-09-30/update-meter-usage-fields
    Request renames: start_time -> starts_at, end_time -> ends_at,
    meters.meter_id -> meters.meter.
    Response renames: data_refreshed_at -> refreshed_at,
    bucket_start_time -> starts_at, bucket_end_time -> ends_at,
    bucket_value -> value, meter_id -> meter.
    Renames come from Stripe's own changelog mapping in the spec file,
    NOT from string similarity - similarity alone fails here
    (e.g. start_time -> starts_at is only 0.74 similar).
  * AST-GUIDED patching, not global string replacement. The tool walks
    the AST and patches ONLY:
      - Call keyword argument names (client.retrieve(start_time=...)),
      - Dict keys ({"meter_id": ...} in a request payload or test stub),
      - Subscript string keys (response["data_refreshed_at"]).
    It does NOT touch docstrings, comments, function parameter names,
    or other string literals. That precision is the point: v1's global
    replace would have rewritten a docstring mentioning an old field.
  * A second change type, handled by REFUSING to auto-patch it. The
    `data` response field is removed and nested inside `rows` - a
    structural change, not a rename. The tool flags it in the PR as
    "manual review required" and leaves that access untouched, rather
    than silently deleting code. Patch safety means knowing when NOT
    to patch.

Pipeline:
  1. Load old/new vendor specs (simplified, sourced from Stripe docs).
  2. Diff request + response properties; apply the changelog rename
     mapping; report renames, removals, and structural changes.
  3. AST-scan the repo for the exact locations above.
  4. On a NEW git branch (main/master untouched), apply edits at those
     exact AST locations only, run the tests, write PR summary + diff.
  5. Stop. A human reviews and merges. The tool never merges to main.

Usage:
  python3 maintainer.py --old specs/spec_old.json --new specs/spec_new.json \
      --repo sample_repo --branch fix/stripe-meter-usage-2025-09-30
"""
import argparse
import ast
import json
import subprocess
import sys
from pathlib import Path


def load_spec(path):
    with open(path) as f:
        return json.load(f)


def diff_specs(old, new):
    """Return (renames, removals, structural_notes) for all endpoints."""
    renames = []      # (endpoint, section, old, new)
    removals = []     # (endpoint, section, field)
    notes = []
    for endpoint, old_def in old.get("endpoints", {}).items():
        new_def = new.get("endpoints", {}).get(endpoint, {})
        rename_map = new_def.get("renames", {})
        for section in ("request", "response"):
            old_props = old_def.get(section, {}).get("properties", {})
            new_props = new_def.get(section, {}).get("properties", {})
            removed = set(old_props) - set(new_props)
            for field in sorted(removed):
                if field in rename_map:
                    renames.append((endpoint, section, field, rename_map[field]))
                else:
                    removals.append((endpoint, section, field))
    for endpoint, new_def in new.get("endpoints", {}).items():
        for note in new_def.get("structural_notes", []):
            notes.append((endpoint, note))
    return renames, removals, notes


def collect_edits(path, rename_map):
    """AST-guided edits for one file.

    Returns a list of (lineno, col_start, col_end, new_text) plus a
    human-readable list of sites. Only Call keywords, Dict keys, and
    Subscript keys are touched.
    """
    text = path.read_text()
    tree = ast.parse(text)
    edits = []
    sites = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if kw.arg in rename_map:
                    edits.append((
                        kw.lineno, kw.col_offset,
                        kw.col_offset + len(kw.arg), rename_map[kw.arg],
                    ))
                    sites.append(f"{path.name}:{kw.lineno} kwarg {kw.arg}")
        if isinstance(node, ast.Dict):
            for key in node.keys:
                if isinstance(key, ast.Constant) and key.value in rename_map:
                    edits.append((
                        key.lineno, key.col_offset, key.end_col_offset,
                        f'"{rename_map[key.value]}"',
                    ))
                    sites.append(f"{path.name}:{key.lineno} dict-key {key.value}")
        if isinstance(node, ast.Subscript):
            sl = node.slice
            if isinstance(sl, ast.Constant) and sl.value in rename_map:
                edits.append((
                    sl.lineno, sl.col_offset, sl.end_col_offset,
                    f'"{rename_map[sl.value]}"',
                ))
                sites.append(f"{path.name}:{sl.lineno} subscript {sl.value}")
    return edits, sites


def apply_edits(path, edits):
    """Apply edits to a file, sorted from the end so offsets stay valid."""
    lines = path.read_text().splitlines(keepends=True)
    for lineno, start, end, new_text in sorted(
        edits, key=lambda e: (e[0], e[1]), reverse=True
    ):
        line = lines[lineno - 1]
        lines[lineno - 1] = line[:start] + new_text + line[end:]
    path.write_text("".join(lines))


def run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def run_tests(repo):
    result = run([sys.executable, "-m", "pytest", "test_app.py", "-q"], cwd=repo)
    if "No module named pytest" in (result.stdout + result.stderr):
        fallback = (
            "import test_app; "
            "fns=[v for k,v in vars(test_app).items() if k.startswith('test_')]; "
            "[fn() for fn in fns]; print(f'{len(fns)} test(s) passed (no-pytest fallback)')"
        )
        result = run([sys.executable, "-c", fallback], cwd=repo)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--old", required=True)
    parser.add_argument("--new", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--branch", default="fix/vendor-breaking-change")
    args = parser.parse_args()

    old_spec = load_spec(args.old)
    new_spec = load_spec(args.new)
    repo = Path(args.repo).resolve()
    out_dir = Path(__file__).parent / "output"
    out_dir.mkdir(exist_ok=True)

    print(f"Vendor: {new_spec.get('vendor')}")
    print(f"Spec change: {old_spec.get('api_version_old')} -> {new_spec.get('api_version_new')}")
    print(f"Source: {new_spec.get('source')}")
    renames, removals, notes = diff_specs(old_spec, new_spec)
    print(f"\nRenames found: {len(renames)}")
    for endpoint, section, old_name, new_name in renames:
        print(f"  - {endpoint} [{section}] {old_name} -> {new_name}")
    print(f"Removals with no rename (not auto-patched): {len(removals)}")
    for endpoint, section, field in removals:
        print(f"  - {endpoint} [{section}] {field} REMOVED")
    print("Structural changes (manual review required):")
    for endpoint, note in notes:
        print(f"  - {endpoint}: {note}")

    if not renames:
        print("\nNo renames to patch. Stopping before any code change.")
        return 0

    rename_map = {old_name: new_name for _, _, old_name, new_name in renames}
    dirty = (
        run(["git", "diff", "--quiet"], cwd=repo).returncode != 0
        or run(["git", "diff", "--cached", "--quiet"], cwd=repo).returncode != 0
    )
    if dirty:
        print("\nRepo has uncommitted tracked changes - refusing to patch.")
        return 1
    run(["git", "checkout", "-b", args.branch], cwd=repo)
    print(f"\nCreated branch: {args.branch} (master untouched)")

    patched_files, all_sites = [], []
    for path in sorted(repo.rglob("*.py")):
        if ".git" in path.parts:
            continue
        edits, sites = collect_edits(path, rename_map)
        if edits:
            apply_edits(path, edits)
            patched_files.append(str(path))
            all_sites.extend(sites)
    print("\nAST-guided patch sites:")
    for site in all_sites:
        print(f"  - {site}")
    print("Note: docstrings, comments, and function parameter names were "
          "deliberately NOT patched - they are not vendor contract.")

    test_result = run_tests(repo)
    print(f"\nTests: exit={test_result.returncode}")
    print(test_result.stdout)
    if test_result.stderr:
        print(test_result.stderr)

    diff_result = run(["git", "diff"], cwd=repo)
    (out_dir / "pr.diff").write_text(diff_result.stdout)
    pr_lines = [
        "# Proposed PR (human review required - NOT merged)",
        "",
        f"Vendor: {new_spec.get('vendor')}",
        f"Spec change: {old_spec.get('api_version_old')} -> {new_spec.get('api_version_new')}",
        f"Source: {new_spec.get('source')}",
        "",
        "## Renames patched (AST-guided, exact call/dict/subscript sites only)",
    ]
    for endpoint, section, old_name, new_name in renames:
        pr_lines.append(f"- {endpoint} [{section}] {old_name} -> {new_name}")
    pr_lines += [
        "",
        "## NOT auto-patched - manual review required",
    ]
    for endpoint, section, field in removals:
        pr_lines.append(f"- {endpoint} [{section}] {field} removed with no rename")
    for endpoint, note in notes:
        pr_lines.append(f"- {endpoint}: {note}")
    pr_lines += ["", "## Files patched"]
    for f in sorted(set(patched_files)):
        pr_lines.append(f"- {f}")
    pr_lines += [
        "",
        "## Patch sites",
    ]
    for site in all_sites:
        pr_lines.append(f"- {site}")
    pr_lines += [
        "",
        f"## Tests: exit code {test_result.returncode}",
        "",
        "```",
        test_result.stdout.strip(),
        "```",
        "",
        "## How to merge (human only)",
        "1. Review output/pr.diff",
        "2. Resolve the manual-review items above (especially the data -> rows nesting)",
        "3. Run the tests yourself",
        f"4. Commit and open a PR from branch `{args.branch}`, or merge manually",
        "This tool never merges to master.",
    ]
    (out_dir / "PR.md").write_text("\n".join(pr_lines) + "\n")
    print("\nPR summary written to output/PR.md")
    print("Diff written to output/pr.diff")
    print(f"Repo is now on branch {args.branch} with uncommitted patch - review, then merge yourself.")
    return 0 if test_result.returncode == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
