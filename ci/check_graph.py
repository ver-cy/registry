#!/usr/bin/env python3
"""check_graph: MMDG graph integrity (ELMM-I11, I16, I17, I18, I19).

Checks, each failing closed with a precise diagnostic:

  (a) referential integrity (ELMM-I19): every edge from and to is a registered
      entry id.
  (b) export coverage (ELMM-I11, ELMM-I19): every entry in an edge's kinds
      appears in the target record's exports. The MMDG is statically computable
      from records alone, so a reference to an unexported kind is rejected here,
      before resolve time.
  (c) declared_min agreement (ELMM-I11): where a from-record's requires names
      the same target and kind as an edge, the edge's declared_min equals that
      requires min_version. declared_min is the sole resolver input under
      Minimal Version Selection (ARCH-002); this keeps the record and the edge
      in lockstep.
  (d) acyclicity of the composes subgraph (ELMM-I16).
  (e) no composes edge leaves the kernel node (ELMM-I18): a role kernel node
      orchestrates nothing; its knowledge of models comes from the registry,
      never from outgoing edges.
  (f) single node per major identity (ELMM-I17): no two records share an id.

Usage:
    python check_graph.py [--root <registry-root>]
"""

import argparse
import sys

import _common as c


def _check_unique_ids(entries):
    # (f) single node per major identity: no two records share an id.
    seen = {}
    for path, record in entries:
        entry_id = record.get("id")
        if entry_id is None:
            raise c.CheckError("entry has no id: " + path)
        if entry_id in seen:
            raise c.CheckError(
                "duplicate registry id " + entry_id + " (ELMM-I17, single node per"
                + " major identity): " + seen[entry_id] + " and " + path
            )
        seen[entry_id] = path
    c.ok("single node per major identity: " + str(len(seen)) + " distinct ids")


def _check_referential_integrity(edges, edges_file, ids):
    # (a) every edge endpoint is a registered id.
    for index, edge in enumerate(edges):
        for role_field in ("from", "to"):
            endpoint = edge.get(role_field)
            if endpoint not in ids:
                raise c.CheckError(
                    "edge #" + str(index) + " in " + edges_file + " has "
                    + role_field + " = " + repr(endpoint) + ", which is not a"
                    + " registered entry id (ELMM-I19, referential integrity)"
                )
    c.ok("referential integrity: all " + str(len(edges)) + " edges resolve to registered ids")


def _check_export_coverage(edges, records_by_id):
    # (b) every kind an edge references is exported by the target.
    for index, edge in enumerate(edges):
        target = records_by_id[edge["to"]]
        exports = set(target.get("exports", []) or [])
        for kind in edge.get("kinds", []) or []:
            if kind not in exports:
                raise c.CheckError(
                    "edge #" + str(index) + " (" + edge["from"] + " -"
                    + edge.get("edge_type", "?") + "-> " + edge["to"] + ") references"
                    + " kind " + repr(kind) + " which is not in " + edge["to"]
                    + " exports " + repr(sorted(exports))
                    + " (ELMM-I11, export coverage)"
                )
    c.ok("export coverage: every referenced kind is exported by its target")


def _check_declared_min_agreement(entries, edges):
    # (c) where a record's requires names the same target and kind as an edge,
    # the edge declared_min equals that min_version.
    by_from = {}
    for edge in edges:
        by_from.setdefault(edge["from"], []).append(edge)
    checked = 0
    for path, record in entries:
        entry_id = record.get("id")
        for req in record.get("requires", []) or []:
            target = req.get("id")
            kind = req.get("kind")
            wanted = req.get("min_version")
            for edge in by_from.get(entry_id, []):
                if edge.get("to") != target:
                    continue
                edge_kinds = edge.get("kinds")
                if edge_kinds and kind not in edge_kinds:
                    continue
                declared_min = edge.get("declared_min")
                if declared_min != wanted:
                    raise c.CheckError(
                        "declared_min disagreement (ELMM-I11): entry " + str(entry_id)
                        + " requires " + str(target) + " kind " + str(kind)
                        + " at min_version " + repr(wanted) + ", but the "
                        + str(edge.get("edge_type", "?")) + " edge to " + str(target)
                        + " declares declared_min " + repr(declared_min)
                        + ". The edge is the sole resolver input; record and edge"
                        + " must agree."
                    )
                checked += 1
    c.ok("declared_min agreement: " + str(checked) + " requires/edge pairs in lockstep")


def _check_no_kernel_composes(edges, records_by_id):
    # (e) no composes edge has from == a role kernel node.
    for index, edge in enumerate(edges):
        if edge.get("edge_type") != "composes":
            continue
        source = records_by_id[edge["from"]]
        if source.get("role") == "kernel":
            raise c.CheckError(
                "edge #" + str(index) + " is a composes edge from the kernel node "
                + edge["from"] + " (ELMM-I18): the kernel orchestrates nothing and"
                + " declares no outgoing composes edge"
            )
    c.ok("kernel isolation: no composes edge leaves a role kernel node")


def _check_composes_acyclic(edges):
    # (d) the composes subgraph is a DAG.
    adjacency = {}
    for edge in edges:
        if edge.get("edge_type") == "composes":
            adjacency.setdefault(edge["from"], []).append(edge["to"])

    WHITE, GREY, BLACK = 0, 1, 2
    color = {}
    for node in adjacency:
        color.setdefault(node, WHITE)
        for target in adjacency[node]:
            color.setdefault(target, WHITE)

    def visit(node, stack):
        color[node] = GREY
        stack.append(node)
        for target in adjacency.get(node, []):
            state = color.get(target, WHITE)
            if state == GREY:
                cycle = stack[stack.index(target):] + [target]
                raise c.CheckError(
                    "cycle in the composes subgraph (ELMM-I16): "
                    + " -> ".join(cycle)
                )
            if state == WHITE:
                visit(target, stack)
        stack.pop()
        color[node] = BLACK

    for node in list(color.keys()):
        if color[node] == WHITE:
            visit(node, [])
    c.ok("acyclicity: the composes subgraph is a DAG")


def run(root):
    c.info("check_graph: MMDG graph integrity")
    c.info("  root: " + root)

    entries = c.load_entries(root)
    edges_file, edges = c.load_edges(root)
    records_by_id = {record.get("id"): record for _path, record in entries}
    ids = set(records_by_id)

    # (f) then (a): establish a clean id set before any lookup by endpoint.
    _check_unique_ids(entries)
    _check_referential_integrity(edges, edges_file, ids)
    # (b), (c), (e), (d): safe now that every endpoint resolves.
    _check_export_coverage(edges, records_by_id)
    _check_declared_min_agreement(entries, edges)
    _check_no_kernel_composes(edges, records_by_id)
    _check_composes_acyclic(edges)

    c.info(
        "check_graph: PASS ("
        + str(len(entries)) + " nodes, " + str(len(edges)) + " edges)"
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description="ELMM registry graph check")
    parser.add_argument("--root", default=None, help="registry root directory")
    args = parser.parse_args(argv)
    try:
        run(c.registry_root(args.root))
        return 0
    except c.CheckError as exc:
        sys.stderr.write("check_graph: FAIL\n" + str(exc) + "\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
