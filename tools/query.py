#!/usr/bin/env python3
"""query: a small CLI over index/unified-index.json.

Filters the unified index by any combination of facets, printing the matching
entries and a count line. Filters combine with AND: an entry must satisfy every
supplied flag to match.

Flags:

  --industry CODE     keep entries carrying this industry code.
  --cluster CODE      keep entries carrying this cluster code.
  --role Rn           keep entries with this compositional role (external only).
  --origin ORIGIN     keep entries with this origin (internal or external).
  --link-type TYPE    keep entries with this default link type (external only).
  --group NAME        keep entries whose Group is exactly NAME (external only).
  --list-facets       print the facet histograms instead of running a query.

A query over valid values always exits 0, even when nothing matches. Supplying a
flag value that is not present in the index (an unknown industry, cluster, role,
origin, link type or group) exits non-zero with a helpful message.

Runtime dependencies: Python 3 standard library only.
"""

import argparse
import json
import os
import sys

FACET_ORDER = ("by_industry", "by_cluster", "by_role", "by_origin", "by_link_type")

FACET_LABELS = {
    "by_industry": "industry",
    "by_cluster": "cluster",
    "by_role": "compositional role",
    "by_origin": "origin",
    "by_link_type": "link type",
}


def registry_root(explicit=None):
    if explicit:
        return os.path.abspath(explicit)
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(here, os.pardir))


def default_index_path():
    return os.path.join(registry_root(), "index", "unified-index.json")


def die(message, code=2):
    sys.stderr.write("query: " + message + "\n")
    return code


def load_index(path):
    if not os.path.isfile(path):
        raise SystemExit(die(
            "index not found: " + path + " (run tools/build_index.py first)", 2))
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except json.JSONDecodeError as exc:
        raise SystemExit(die("index is not valid JSON: " + str(exc), 2))
    if not isinstance(data, dict) or "entries" not in data:
        raise SystemExit(die("index is malformed (no entries): " + path, 2))
    return data


def facet_keys(index, facet):
    facets = index.get("facets", {})
    hist = facets.get(facet, {})
    return set(hist.keys()) if isinstance(hist, dict) else set()


def known_groups(index):
    groups = set()
    for entry in index.get("entries", []):
        if "group" in entry:
            groups.add(entry["group"])
    return groups


def validate_value(index, facet, value, label):
    """Exit non-zero when value is absent from the given facet histogram."""
    keys = facet_keys(index, facet)
    if value not in keys:
        options = ", ".join(sorted(keys)) if keys else "(none in index)"
        raise SystemExit(die(
            "unknown " + label + " " + repr(value)
            + "; not present in the index. Known values: " + options, 2))


def matches(entry, args):
    if args.industry is not None and args.industry not in entry.get("industry", []):
        return False
    if args.cluster is not None and args.cluster not in entry.get("cluster", []):
        return False
    if args.role is not None and entry.get("role") != args.role:
        return False
    if args.origin is not None and entry.get("origin") != args.origin:
        return False
    if args.link_type is not None and entry.get("link_type") != args.link_type:
        return False
    if args.group is not None and entry.get("group") != args.group:
        return False
    return True


def print_facets(index):
    facets = index.get("facets", {})
    totals = index.get("totals", {})
    sys.stdout.write(
        "totals: internal=" + str(totals.get("internal", 0))
        + " external=" + str(totals.get("external", 0))
        + " total=" + str(totals.get("total", 0)) + "\n"
    )
    for facet in FACET_ORDER:
        hist = facets.get(facet, {})
        sys.stdout.write("\n" + facet + " (" + FACET_LABELS[facet] + "):\n")
        if not hist:
            sys.stdout.write("  (empty)\n")
            continue
        width = max(len(str(k)) for k in hist)
        for code in sorted(hist):
            sys.stdout.write("  " + str(code).ljust(width) + "  " + str(hist[code]) + "\n")


def print_matches(rows):
    if rows:
        ref_w = max(len(r["ref"]) for r in rows)
        origin_w = max(len(r.get("origin", "")) for r in rows)
        for r in rows:
            industry = ";".join(r.get("industry", []))
            sys.stdout.write(
                r["ref"].ljust(ref_w) + "  "
                + r.get("origin", "").ljust(origin_w) + "  "
                + r.get("name", "")
                + ("  [" + industry + "]" if industry else "")
                + "\n"
            )
    sys.stdout.write(str(len(rows)) + " entries matched\n")


def build_parser():
    parser = argparse.ArgumentParser(description="Query the unified registry index")
    parser.add_argument("--index", default=None, help="path to unified-index.json")
    parser.add_argument("--industry", default=None, help="industry code")
    parser.add_argument("--cluster", default=None, help="cluster code")
    parser.add_argument("--role", default=None, help="compositional role, R1 to R8")
    parser.add_argument("--origin", default=None, choices=None, help="internal or external")
    parser.add_argument("--link-type", dest="link_type", default=None, help="default link type")
    parser.add_argument("--group", default=None, help="external-registry Group name")
    parser.add_argument("--list-facets", action="store_true", help="print facet histograms and exit")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    index_path = args.index or default_index_path()
    index = load_index(index_path)

    if args.list_facets:
        print_facets(index)
        return 0

    if args.industry is not None:
        validate_value(index, "by_industry", args.industry, "industry")
    if args.cluster is not None:
        validate_value(index, "by_cluster", args.cluster, "cluster")
    if args.role is not None:
        validate_value(index, "by_role", args.role, "compositional role")
    if args.origin is not None:
        validate_value(index, "by_origin", args.origin, "origin")
    if args.link_type is not None:
        validate_value(index, "by_link_type", args.link_type, "link type")
    if args.group is not None:
        groups = known_groups(index)
        if args.group not in groups:
            options = ", ".join(sorted(groups)) if groups else "(none in index)"
            raise SystemExit(die(
                "unknown group " + repr(args.group)
                + "; not present in the index. Known values: " + options, 2))

    rows = [entry for entry in index.get("entries", []) if matches(entry, args)]
    print_matches(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
