#!/usr/bin/env python3
"""check_schema: V0 schema validation of the registry (ELMM-I8, ELMM-I14).

Validates:

  - every registry entry (entries/*.yaml) against the registry node profile
    schema (registry-node.schema.json). The node profile carries the MMDG node
    constraints and binds the upstream Meta-Universe registry entry fields by
    reference, so validation is offline and deterministic (the referenced
    upstream schema is vendored under the schema directory).
  - when a copy of the upstream entry schema is vendored under the schema
    directory (by its Meta-Universe $id), the upstream-field projection of
    every entry against it, as an explicit convergence proof. The full record
    is not offered to the upstream schema: upstream is
    additionalProperties:false and the profile extension fields (role, exports,
    requires, sync_contract) and profile-local fields are pending upstream
    change requests CR-1 and CR-2. The projection keeps only the upstream field
    set, and that projection is green against the unmodified upstream schema.
  - every edge in mmdg/edges.json against the edge schema (mmdg-edge.schema.json).

Exits non-zero with a precise message on the first violation. This is the V0
rung of the admission gate (ELMM-I39): fail closed on the write path.

Usage:
    python check_schema.py [--root <registry-root>]

The root defaults to the parent of this script's directory, so the check is
working directory independent and reusable on a copied tree.
"""

import argparse
import sys

import _common as c


def run(root):
    c.info("check_schema: schema validation (ELMM-I8, ELMM-I14)")
    c.info("  root: " + root)

    store, by_name = c.load_schema_store(root)
    node_schema = c.pick_schema(by_name, c.NODE_SCHEMA_NAMES, "MMDG node profile")
    edge_schema = c.pick_schema(by_name, c.EDGE_SCHEMA_NAMES, "MMDG edge")
    # The upstream entry schema is bound by reference from the node profile, so
    # it is normally vendored. When present we additionally prove convergence on
    # the upstream-field projection of each record (see module docstring).
    upstream_schema = store.get(c.UPSTREAM_ENTRY_ID)
    if upstream_schema is not None:
        c.info(
            "  upstream entry schema found; proving convergence on the"
            + " upstream-field projection of each entry"
        )
    else:
        c.info("  upstream entry schema not vendored; validating the node profile only")

    entries = c.load_entries(root)
    for path, record in entries:
        subject = "entry " + record.get("id", "(missing id)") + " [" + path + "]"
        # The full record is a valid MMDG node profile record.
        c.validate_or_raise(node_schema, record, store, subject, "registry-node schema")
        # Convergence proof: the upstream-field projection is a valid upstream
        # registry entry. The extension fields are held back pending CR-1/CR-2.
        if upstream_schema is not None:
            projection = c.project_to_upstream(record, upstream_schema)
            c.validate_or_raise(
                upstream_schema, projection, store,
                subject + " (upstream field projection)", "upstream entry.schema.json",
            )
            c.ok(subject + " valid against the node profile and, projected, the upstream entry schema")
        else:
            c.ok(subject + " valid against the registry node profile schema")

    edges_file, edges = c.load_edges(root)
    for index, edge in enumerate(edges):
        label = edge.get("edge_type", "?")
        subject = (
            "edge #" + str(index) + " "
            + str(edge.get("from", "?")) + " -" + str(label) + "-> "
            + str(edge.get("to", "?")) + " [" + edges_file + "]"
        )
        c.validate_or_raise(edge_schema, edge, store, subject, "mmdg-edge schema")
        c.ok(subject + " valid against edge schema")

    c.info(
        "check_schema: PASS ("
        + str(len(entries)) + " entries, " + str(len(edges)) + " edges)"
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description="ELMM registry schema check")
    parser.add_argument("--root", default=None, help="registry root directory")
    args = parser.parse_args(argv)
    try:
        run(c.registry_root(args.root))
        return 0
    except c.CheckError as exc:
        sys.stderr.write("check_schema: FAIL\n" + str(exc) + "\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
