#!/usr/bin/env python3
"""check_zero_change: the zero-change registration guarantee (ELMM-I7, ELMM-I44).

Registering a new meta-model of any role and any domain must require zero
changes to kernel code, kernel schemas and kernel vocabulary: only registry
data (a Model Registration Record plus edges) is added. This check proves it
mechanically.

Procedure:

  1. Copy the whole registry tree to a temporary directory.
  2. Add a NEW dummy Core record (vercy.demo, role core, exports demo-kind) by
     cloning the shape of an existing Core entry, so the dummy is valid against
     exactly the same schemas the seed entries satisfy, then overriding only its
     identity, exports and requires. Add one references edge from vercy.plmm to
     vercy.demo naming demo-kind.
  3. Run check_schema and check_graph and the resolver against the temp tree.
     All must pass, and the resolver must resolve a task that reaches the new
     kind, with no code change.
  4. Assert that no file under resolver/ or schema/ differs from the original
     (hash the trees before and after). A non-empty kernel diff means the
     registration required a kernel change, which is a conformance failure.

Usage:
    python check_zero_change.py [--root <registry-root>]
"""

import argparse
import json
import os
import shutil
import sys
import tempfile

import yaml

import _common as c

DEMO_ID = "vercy.demo"
DEMO_NAMESPACE = "demo"
DEMO_CSN = "demo-core-model"
DEMO_KIND = "demo-kind"
DEMO_VERSION = "0.1.0"
DEMO_FINGERPRINT = "mufp:00000000demo0000"
# A fixed instant for the injected edge; determinism forbids a wall clock read.
DEMO_OBSERVED_AT = "2026-08-10T00:00:00Z"


def _pick_core_template(entries):
    """Return a parsed Core (or any) entry to clone the converged shape from."""
    for _path, record in entries:
        if record.get("role") == "core":
            return record
    # Fall back to any entry: we only reuse its field shape, not its identity.
    return entries[0][1]


def _build_demo_record(template):
    record = json.loads(json.dumps(template))  # deep copy of the converged shape
    record["id"] = DEMO_ID
    record["csn"] = DEMO_CSN
    record["primary_namespace"] = DEMO_NAMESPACE
    record["role"] = "core"
    record["version"] = DEMO_VERSION
    record["fingerprint"] = DEMO_FINGERPRINT
    # Keep the template's lifecycle status verbatim (the seed uses the profile
    # lifecycle vocabulary, where a released, in-use model is "active"); do not
    # invent a value the node schema might not accept.
    record["exports"] = [DEMO_KIND]
    record["requires"] = []
    record["display_alias"] = "DEMO"
    # Routing hints, if the template carried any, do not apply to the dummy.
    record.pop("routing_hints", None)
    # Human readable fields, present only when the converged schema carries them.
    if "name" in record:
        record["name"] = "Demo Core Model"
    if "purpose" in record:
        record["purpose"] = "Synthetic core model for the zero-change registration test."
    if isinstance(record.get("source"), dict):
        record["source"]["repository"] = "https://github.com/ver-cy/demo"
        record["source"]["ref"] = "v" + DEMO_VERSION
        record["source"].pop("path", None)
    record.pop("provenance", None)
    return record


def _build_demo_edge():
    # A references edge from the Landscape to the new Core. references edges
    # require declared_min, compositional_role and kinds (edge schema); demo-kind
    # is covered by the dummy exports, and plmm requires no demo entry so the
    # declared_min agreement check is vacuous for it.
    return {
        "from": "vercy.plmm",
        "to": DEMO_ID,
        "edge_type": "references",
        "declared_min": DEMO_VERSION,
        "compositional_role": "R4",
        "kinds": [DEMO_KIND],
        "fingerprint_at_registration": DEMO_FINGERPRINT,
        "declared_by": "vercy.plmm",
        "observed_at": DEMO_OBSERVED_AT,
        "note": "Synthetic zero-change registration edge; not part of the seed.",
    }


def _zero_change_task():
    # Routes to vercy.plmm via its declared routing hints (plmm.product plus the
    # keyword portfolio), so the transitive walk reaches vercy.demo along the new
    # references edge with no resolver change.
    return {
        "task_ref": "task-zero-change-0001",
        "purpose": "Zero-change registration test: portfolio impact reaching a new domain",
        "requester_identity": "agent:zero-change-test",
        "referenced_entities": ["plmm.product"],
        "max_tokens": 6000,
    }


def _run_check(script_name, temp_root):
    ci_dir = os.path.dirname(os.path.abspath(__file__))
    script = os.path.join(ci_dir, script_name)
    import subprocess
    proc = subprocess.run(
        [sys.executable, script, "--root", temp_root],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    return proc.returncode, proc.stdout.decode("utf-8", "replace"), proc.stderr.decode("utf-8", "replace")


def run(root):
    c.info("check_zero_change: zero-change registration guarantee (ELMM-I7, ELMM-I44)")
    c.info("  root: " + root)

    # Baseline kernel hashes, taken from the original tree.
    original_schema_hashes = c.hash_tree(c.schema_dir(root))
    original_resolver_hashes = c.hash_tree(os.path.join(root, "resolver"))
    if not original_schema_hashes:
        raise c.CheckError("no schema files found under the registry schema directory")
    if not original_resolver_hashes:
        raise c.CheckError("no resolver files found under the registry resolver directory")

    entries = c.load_entries(root)
    template = _pick_core_template(entries)

    temp_parent = tempfile.mkdtemp(prefix="elmm-zero-change-")
    temp_root = os.path.join(temp_parent, "registry")
    try:
        shutil.copytree(root, temp_root)

        # Step 2: inject the dummy record and edge into the copied tree only.
        demo_record = _build_demo_record(template)
        demo_path = os.path.join(c.entries_dir(temp_root), DEMO_ID + ".yaml")
        with open(demo_path, "w", encoding="utf-8") as handle:
            handle.write("# Synthetic zero-change registration fixture (not part of the seed).\n")
            yaml.safe_dump(demo_record, handle, sort_keys=False, allow_unicode=True)

        edges_file, edges = c.load_edges(temp_root)
        edges.append(_build_demo_edge())
        with open(edges_file, "w", encoding="utf-8") as handle:
            json.dump(edges, handle, indent=2)
            handle.write("\n")

        task_path = os.path.join(c.examples_dir(temp_root), "task-zero-change.json")
        with open(task_path, "w", encoding="utf-8") as handle:
            json.dump(_zero_change_task(), handle, indent=2)
            handle.write("\n")

        c.ok("injected dummy Core record " + DEMO_ID + " and one references edge from vercy.plmm")

        # Step 3: the two admission checks must pass on the extended registry.
        for script in ("check_schema.py", "check_graph.py"):
            code, out, err = _run_check(script, temp_root)
            if code != 0:
                raise c.CheckError(
                    "registering " + DEMO_ID + " failed " + script + " (exit "
                    + str(code) + "):\n" + (err.strip() or out.strip() or "(no output)")
                )
            c.ok(script + " passes with the new domain registered")

        # ... and the resolver resolves a task naming the new kind, no code change.
        resolver = c.resolver_path(temp_root)
        code, out, err = c.run_resolver(temp_root, task_path, c.OBSERVED_AT, resolver=resolver)
        if code != 0:
            raise c.CheckError(
                "the resolver failed on a task reaching " + DEMO_ID + " (exit "
                + str(code) + "):\n" + (err.strip() or "(no stderr)")
            )
        pack, snapshot = c.extract_pack_and_snapshot(out, "zero-change resolution")
        resolved_ids = {r.get("id") for r in snapshot.get("resolved", [])}
        if DEMO_ID not in resolved_ids:
            raise c.CheckError(
                "the resolver ran but did not resolve the new domain " + DEMO_ID
                + "; resolved set was " + repr(sorted(resolved_ids))
                + ". The zero-change edge did not take effect."
            )
        c.ok("resolver resolves a task reaching " + DEMO_ID + " with no code change")

        # Step 4: prove the kernel is byte for byte unchanged.
        after_schema_hashes = c.hash_tree(c.schema_dir(temp_root))
        after_resolver_hashes = c.hash_tree(os.path.join(temp_root, "resolver"))
        if after_schema_hashes != original_schema_hashes:
            raise c.CheckError(
                "registration changed files under schema/ (ELMM-I7 violated): "
                + repr(_diff_trees(original_schema_hashes, after_schema_hashes))
            )
        if after_resolver_hashes != original_resolver_hashes:
            raise c.CheckError(
                "registration changed files under resolver/ (ELMM-I7 violated): "
                + repr(_diff_trees(original_resolver_hashes, after_resolver_hashes))
            )
        c.ok("kernel diff empty: schema/ and resolver/ are byte for byte unchanged")

        c.info("check_zero_change: PASS (new domain registered with zero kernel change)")
    finally:
        shutil.rmtree(temp_parent, ignore_errors=True)


def _diff_trees(before, after):
    changed = []
    for rel in sorted(set(before) | set(after)):
        if before.get(rel) != after.get(rel):
            changed.append(rel)
    return changed


def main(argv=None):
    parser = argparse.ArgumentParser(description="ELMM zero-change registration check")
    parser.add_argument("--root", default=None, help="registry root directory")
    args = parser.parse_args(argv)
    try:
        run(c.registry_root(args.root))
        return 0
    except c.CheckError as exc:
        sys.stderr.write("check_zero_change: FAIL\n" + str(exc) + "\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
