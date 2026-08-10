#!/usr/bin/env python3
"""import_external: build external/external-standards.csv from the source catalogue.

Reads two authored inputs:

  external/external-models.source.csv  the source external-standards catalogue
                                       (one row per standard, columns fixed).
  facets/group-industry-map.csv        maps each external-registry Group to one
                                       or more vercy-industry codes, semicolon
                                       separated.

and writes one generated output:

  external/external-standards.csv      every source row, verbatim, with two
                                       added columns: Origin (always "external")
                                       and Industry (the semicolon-joined
                                       industry codes for that row's Group).

The industry codes are validated against the industry facet vocabulary
(facets/industry.yaml). The build is deterministic and idempotent: source
columns keep their original order, then Origin, then Industry; rows are sorted
by (Group, Acronym, Name); the writer uses an LF line terminator and minimal
quoting. Re-running yields a byte-identical file.

The tool exits non-zero with a clear diagnostic when any Group is missing from
the map or any mapped code is not a known industry code.

Runtime dependencies: Python 3 standard library plus PyYAML. No others.
"""

import argparse
import csv
import os
import sys

try:
    import yaml
except ImportError as exc:  # pragma: no cover - environment guard
    sys.stderr.write("FAIL: PyYAML is required (pip install pyyaml): " + str(exc) + "\n")
    raise

ORIGIN_VALUE = "external"

# Cells in the source catalogue that are exactly a lone dash glyph are the
# source's placeholder for "none" or "not applicable". They are normalized to an
# empty string on import: an empty cell is the honest representation of no value,
# and it keeps the published catalogue free of stray dash glyphs. Genuine dashes
# inside longer values (a standard's name, a list of similar models) are content
# and are preserved verbatim.
PLACEHOLDER_DASHES = {"—", "–", "-"}


def clean_cell(value):
    """Return the cell value, with a lone dash placeholder normalized to empty."""
    if value is None:
        return ""
    if value.strip() in PLACEHOLDER_DASHES:
        return ""
    return value


def registry_root(explicit=None):
    """Return the registry root directory.

    When explicit is given it is used verbatim. Otherwise the root is the parent
    of the directory holding this module (the tools live in <root>/tools/), which
    matches the ci/_common.py convention and makes the tool path independent.
    """
    if explicit:
        return os.path.abspath(explicit)
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(here, os.pardir))


def fail(message):
    sys.stderr.write("FAIL: " + message + "\n")
    raise SystemExit(1)


def load_industry_codes(root):
    """Return the set of known industry codes from facets/industry.yaml."""
    path = os.path.join(root, "facets", "industry.yaml")
    if not os.path.isfile(path):
        fail("industry vocabulary not found: " + path)
    with open(path, "r", encoding="utf-8") as handle:
        doc = yaml.safe_load(handle)
    if not isinstance(doc, dict) or not isinstance(doc.get("industries"), list):
        fail("industry vocabulary is malformed (expected an industries list): " + path)
    codes = set()
    for item in doc["industries"]:
        if isinstance(item, dict) and "code" in item:
            codes.add(str(item["code"]))
    if not codes:
        fail("industry vocabulary declares no codes: " + path)
    return codes


def load_group_map(root):
    """Return an ordered mapping Group -> list of industry codes."""
    path = os.path.join(root, "facets", "group-industry-map.csv")
    if not os.path.isfile(path):
        fail("group-industry map not found: " + path)
    mapping = {}
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or "Group" not in reader.fieldnames or "Industries" not in reader.fieldnames:
            fail("group-industry map must have columns Group,Industries: " + path)
        for row in reader:
            group = (row.get("Group") or "").strip()
            if not group:
                continue
            raw = row.get("Industries") or ""
            codes = [part.strip() for part in raw.split(";")]
            codes = [c for c in codes if c]
            if not codes:
                fail("group-industry map has no codes for Group " + repr(group))
            if group in mapping:
                fail("group-industry map lists Group " + repr(group) + " more than once")
            mapping[group] = codes
    if not mapping:
        fail("group-industry map is empty: " + path)
    return mapping


def read_source(root):
    """Return (columns, rows) from the source catalogue, values verbatim."""
    path = os.path.join(root, "external", "external-models.source.csv")
    if not os.path.isfile(path):
        fail("source catalogue not found: " + path)
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            fail("source catalogue has no header row: " + path)
        columns = list(reader.fieldnames)
        for reserved in ("Origin", "Industry"):
            if reserved in columns:
                fail("source catalogue already has a reserved column " + repr(reserved))
        for required in ("Group", "Acronym", "Name"):
            if required not in columns:
                fail("source catalogue is missing the required column " + repr(required))
        rows = []
        for record in reader:
            if record.get(None) is not None:
                fail("source catalogue has a row with more fields than the header")
            rows.append({col: clean_cell(record.get(col)) for col in columns})
    return columns, rows


def build_rows(columns, rows, group_map, known_codes):
    """Return the output columns and the sorted, faceted output rows."""
    out_columns = list(columns) + ["Origin", "Industry"]
    missing_groups = set()
    unknown_pairs = set()
    out_rows = []
    for record in rows:
        group = record.get("Group", "")
        codes = group_map.get(group)
        if codes is None:
            missing_groups.add(group)
            continue
        bad = [c for c in codes if c not in known_codes]
        for c in bad:
            unknown_pairs.add((group, c))
        if bad:
            continue
        out = dict(record)
        out["Origin"] = ORIGIN_VALUE
        out["Industry"] = ";".join(codes)
        out_rows.append(out)

    if missing_groups:
        listing = ", ".join(repr(g) for g in sorted(missing_groups))
        fail("the following Group values are absent from the group-industry map: " + listing)
    if unknown_pairs:
        listing = ", ".join(
            repr(code) + " (Group " + repr(group) + ")"
            for group, code in sorted(unknown_pairs)
        )
        fail("the group-industry map references unknown industry codes: " + listing)

    out_rows.sort(key=lambda r: (r.get("Group", ""), r.get("Acronym", ""), r.get("Name", "")))
    return out_columns, out_rows


def write_output(root, out_columns, out_rows):
    path = os.path.join(root, "external", "external-standards.csv")
    directory = os.path.dirname(path)
    if not os.path.isdir(directory):
        os.makedirs(directory)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
        writer.writerow(out_columns)
        for record in out_rows:
            writer.writerow([record.get(col, "") for col in out_columns])
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build external/external-standards.csv from the source catalogue")
    parser.add_argument("--root", default=None, help="registry root directory (default: parent of tools/)")
    args = parser.parse_args(argv)

    root = registry_root(args.root)
    known_codes = load_industry_codes(root)
    group_map = load_group_map(root)
    columns, rows = read_source(root)
    out_columns, out_rows = build_rows(columns, rows, group_map, known_codes)
    path = write_output(root, out_columns, out_rows)
    sys.stdout.write(
        "wrote " + path + ": " + str(len(out_rows)) + " rows, "
        + str(len(out_columns)) + " columns (source + Origin + Industry)\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
