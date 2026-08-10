#!/usr/bin/env python3
"""check_resolve: resolver determinism and output validity (ELMM-I23, I26, I30).

For every task descriptor under examples/task-*.json:

  1. Optionally validate the descriptor against task-descriptor.schema.json.
  2. Run the resolver twice with the same FIXED --observed-at and assert the two
     runs are byte identical. Determinism is mandatory (ELMM-I23): no wall clock,
     no random; the same registry state and the same request yield the same
     Twin Composition Snapshot every time.
  3. Assert the emitted context pack validates against context-pack.schema.json
     and the emitted Twin Composition Snapshot validates against
     twin-snapshot.schema.json (ELMM-I30, ELMM-I25).
  4. If a committed fixture exists under examples/expected/, assert the fresh
     output equals the fixture (replayability, ELMM-I26).

Resolver contract (see _common): the resolver is invoked as
    python resolve.py --task <task> --registry <root> --observed-at <iso8601> \
        --out-pack <pack.json> --out-snapshot <snapshot.json>
and writes the pack and the Twin Composition Snapshot to those files; CI reads
them back as one canonical {"context_pack": ..., "twin_snapshot": ...} object.
The resolver exits non-zero with a diagnostic on any failure.

Fixture layout under examples/expected/ (any that exist are checked):
    <task-stem>.pack.json       expected context pack
    <task-stem>.snapshot.json   expected Twin Composition Snapshot
    <task-stem>.json            combined {"context_pack":..., "twin_snapshot":...}

Usage:
    python check_resolve.py [--root <registry-root>]
"""

import argparse
import glob
import os
import sys

import _common as c


def _find_tasks(root):
    directory = c.examples_dir(root)
    if not os.path.isdir(directory):
        raise c.CheckError("examples directory not found: " + directory)
    tasks = sorted(glob.glob(os.path.join(directory, "task-*.json")))
    if not tasks:
        raise c.CheckError(
            "no task descriptors found (examples/task-*.json); the worked example"
            + " is the deliverable and the resolver check needs at least one task"
        )
    return tasks


def _compare_to_fixture(root, stem, pack, snapshot):
    expected_dir = os.path.join(c.examples_dir(root), "expected")
    if not os.path.isdir(expected_dir):
        return 0
    checked = 0

    def compare(expected_obj, actual_obj, what):
        if c.canonical_json(expected_obj) != c.canonical_json(actual_obj):
            raise c.CheckError(
                "fresh " + what + " for " + stem + " does not match the committed"
                + " fixture under examples/expected/ (replayability, ELMM-I26)"
            )

    combined = os.path.join(expected_dir, stem + ".json")
    pack_fixture = os.path.join(expected_dir, stem + ".pack.json")
    snap_fixture = os.path.join(expected_dir, stem + ".snapshot.json")

    if os.path.isfile(combined):
        doc = c.load_json_file(combined)
        exp_pack, exp_snapshot = c.extract_pack_and_snapshot(
            c.canonical_json(doc).encode("utf-8"), "fixture " + combined
        )
        compare(exp_pack, pack, "context pack")
        compare(exp_snapshot, snapshot, "twin snapshot")
        checked += 2
    if os.path.isfile(pack_fixture):
        compare(c.load_json_file(pack_fixture), pack, "context pack")
        checked += 1
    if os.path.isfile(snap_fixture):
        compare(c.load_json_file(snap_fixture), snapshot, "twin snapshot")
        checked += 1
    return checked


def run(root):
    c.info("check_resolve: resolver determinism and output validity (ELMM-I23, I30)")
    c.info("  root: " + root)
    c.info("  observed-at (fixed): " + c.OBSERVED_AT)

    store, by_name = c.load_schema_store(root)
    pack_schema = c.pick_schema(by_name, c.PACK_SCHEMA_NAMES, "context pack")
    snapshot_schema = c.pick_schema(by_name, c.SNAPSHOT_SCHEMA_NAMES, "twin snapshot")
    task_schema = None
    for name in c.TASK_SCHEMA_NAMES:
        if name in by_name:
            task_schema = by_name[name]
            break

    tasks = _find_tasks(root)
    for task_path in tasks:
        stem = os.path.splitext(os.path.basename(task_path))[0]
        subject = "task " + stem

        if task_schema is not None:
            descriptor = c.load_json_file(task_path)
            c.validate_or_raise(
                task_schema, descriptor, store, subject, "task-descriptor schema"
            )

        code1, out1, err1 = c.run_resolver(root, task_path, c.OBSERVED_AT)
        if code1 != 0:
            raise c.CheckError(
                subject + ": resolver exited " + str(code1) + " on the first run:\n"
                + (err1.strip() or "(no stderr)")
            )
        code2, out2, err2 = c.run_resolver(root, task_path, c.OBSERVED_AT)
        if code2 != 0:
            raise c.CheckError(
                subject + ": resolver exited " + str(code2) + " on the second run:\n"
                + (err2.strip() or "(no stderr)")
            )

        if out1 != out2:
            raise c.CheckError(
                subject + ": resolver output is not deterministic (ELMM-I23); two"
                + " runs with the same fixed --observed-at produced different bytes"
            )
        c.ok(subject + ": deterministic across two runs (byte identical)")

        pack, snapshot = c.extract_pack_and_snapshot(out1, subject)
        c.validate_or_raise(pack_schema, pack, store, subject + " context pack", "context-pack schema")
        c.validate_or_raise(snapshot_schema, snapshot, store, subject + " snapshot", "twin-snapshot schema")
        c.ok(subject + ": pack and snapshot valid against their schemas")

        fixtures = _compare_to_fixture(root, stem, pack, snapshot)
        if fixtures:
            c.ok(subject + ": matches committed fixture (" + str(fixtures) + " artifacts)")

    c.info("check_resolve: PASS (" + str(len(tasks)) + " task(s))")


def main(argv=None):
    parser = argparse.ArgumentParser(description="ELMM resolver determinism check")
    parser.add_argument("--root", default=None, help="registry root directory")
    args = parser.parse_args(argv)
    try:
        run(c.registry_root(args.root))
        return 0
    except c.CheckError as exc:
        sys.stderr.write("check_resolve: FAIL\n" + str(exc) + "\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
