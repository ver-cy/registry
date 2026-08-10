#!/usr/bin/env python3
"""check_facets: facet vocabulary and generated-artifact integrity.

The fifth admission check. It makes the two facet axes of the unified registry
self-guarding and proves the two generated artifacts are current. The registry
carries two entry classes (internal MMDG nodes under entries/, external
standards under external/external-standards.csv) over two orthogonal facet axes:
the cluster axis (what a thing is, the fifteen ontological clusters) and the
industry axis (which sector uses or governs it, the vercy-industry vocabulary).
government-public-sector is one industry vertical among many, not a privileged
axis (ARCH-017).

Five assertions, each failing closed with a precise diagnostic:

  (a) FACET MEMBERSHIP of internal entries. Every industry[] code on an entry
      exists in facets/industry.yaml and every cluster[] code exists in
      facets/clusters.yaml. The two facet fields are optional (registry-node
      schema v0.2), so a pre-facet entry with neither field is vacuously valid;
      any code that is present must be a known code.

  (b) GROUP MAP COVERAGE. facets/group-industry-map.csv covers EXACTLY the set
      of Groups in external/external-models.source.csv (no missing Group, no
      extra Group), and every industry code it maps exists in
      facets/industry.yaml. Every external standard inherits its industry from
      its Group through this map, so an uncovered Group would leave standards
      unfaceted and an extra Group would be dead mapping.

  (c) IMPORT DRIFT GUARD. The committed external/external-standards.csv is what
      tools/import_external.py produces from the committed source right now.
      Proven by regenerating the file inside a throwaway copy of the tree (the
      generator locates its root from its own file location, the check_facets
      convention shared with check_zero_change) and asserting the regenerated
      bytes equal the committed bytes. The committed file is never touched.

  (d) EXTERNAL ROW VALIDITY. Every row of external/external-standards.csv, taken
      as an object, validates against schema/external-standard.schema.json, and
      every industry code in its Industry column exists in facets/industry.yaml.

  (e) INDEX FRESHNESS GUARD. The committed index/unified-index.json is what
      tools/build_index.py produces from the committed registry right now,
      proven the same way as (c): rebuild inside a throwaway copy and assert the
      rebuilt bytes equal the committed bytes.

Generator contract (shared with check_zero_change's copytree idiom, and with the
determinism mandate ELMM-I23): each generator is a runnable script that locates
the registry root from its own file location and writes its artifact to the
committed path under that root, deterministically (no wall clock, no random), so
a regenerated artifact is byte-identical to the committed one. check_facets does
not pass the generator any flags; it runs the generator inside a temporary copy
of the tree and compares the artifact the generator writes there against the
committed artifact in the real tree.

Usage:
    python check_facets.py [--root <registry-root>]

The root defaults to the parent of this script's directory, so the check is
working directory independent and reusable on a copied tree.
"""

import argparse
import csv
import os
import shutil
import subprocess
import sys
import tempfile

import _common as c


# Repo-relative locations of the facet files, the two external files, the index,
# the external-standard schema, and the two generators. Kept as path segment
# tuples so they join cleanly on any platform (os.path.join, no bash-isms).
INDUSTRY_FACET = ("facets", "industry.yaml")
CLUSTER_FACET = ("facets", "clusters.yaml")
GROUP_MAP = ("facets", "group-industry-map.csv")
EXTERNAL_SOURCE = ("external", "external-models.source.csv")
EXTERNAL_STANDARDS = ("external", "external-standards.csv")
UNIFIED_INDEX = ("index", "unified-index.json")
EXTERNAL_SCHEMA_NAME = "external-standard.schema.json"
IMPORT_TOOL = ("tools", "import_external.py")
BUILD_INDEX_TOOL = ("tools", "build_index.py")

# Column names in the two external CSV files and in the group map.
GROUP_COLUMN = "Group"
MAP_GROUP_COLUMN = "Group"
MAP_INDUSTRIES_COLUMN = "Industries"
ROW_INDUSTRY_COLUMN = "Industry"

# Fixed CSV-header to JSON-key projection for one external-standards.csv row,
# the same lower_snake_case transform documented in external-standard.schema.json
# and applied by tools/import_external.py. check_facets validates the projected
# object, so the mapping lives here verbatim (a generic camel-to-snake transform
# would mangle the acronym-bearing headers URL and URI, so the map is explicit).
# Industry and Cluster project to arrays (the source encodes them as one
# semicolon-separated cell); every other column projects to a string.
EXTERNAL_COLUMN_TO_KEY = {
    "Group": "group",
    "Name": "name",
    "Acronym": "acronym",
    "SpecificationSourceURL": "specification_source_url",
    "Category": "category",
    "ParentModel": "parent_model",
    "SimilarModels": "similar_models",
    "Maintainer": "maintainer",
    "Format": "format",
    "Status": "status",
    "NamespaceURI": "namespace_uri",
    "Year": "year",
    "Notes": "notes",
    "CompositionalRole": "compositional_role",
    "DefaultLinkType": "default_link_type",
    "Origin": "origin",
    "Industry": "industry",
    "Cluster": "cluster",
}
EXTERNAL_ARRAY_KEYS = frozenset(("industry", "cluster"))


# ---------------------------------------------------------------------------
# Small readers (kept local so _common and the existing four checks are untouched)
# ---------------------------------------------------------------------------

def _abspath(root, segments):
    return os.path.join(root, *segments)


def _rel(segments):
    return "/".join(segments)


def _read_bytes(path):
    with open(path, "rb") as handle:
        return handle.read()


def _read_csv(path, subject):
    """Return (fieldnames, list-of-row-dicts) for a committed CSV.

    Uses utf-8-sig so a stray byte order mark on the header does not corrupt the
    first column name, and newline="" so the csv module owns line handling.
    """
    if not os.path.isfile(path):
        raise c.CheckError(subject + " not found: " + path)
    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fieldnames = reader.fieldnames or []
            rows = list(reader)
    except OSError as exc:
        raise c.CheckError("could not read " + subject + " (" + path + "): " + str(exc))
    return fieldnames, rows


def _split_codes(cell):
    """Split a semicolon-separated code cell into a stable list of codes.

    The group map and the generated Industry column both encode multiple codes
    as a single semicolon-separated field. Empty fragments are dropped.
    """
    if cell is None:
        return []
    return [part.strip() for part in cell.split(";") if part.strip()]


def _load_code_set(root, segments, list_keys, label):
    """Load the closed code set from a facet vocabulary YAML file.

    The industry facet lists its codes under industries:, each a mapping with a
    code: field; the cluster facet mirrors world-models under clusters:. This
    reader accepts either a list of mappings with a code field or a plain list of
    string codes, so a facet file authored in either shape is read correctly.
    """
    path = _abspath(root, segments)
    if not os.path.isfile(path):
        raise c.CheckError(
            "the " + label + " facet vocabulary is missing: " + path
            + ". check_facets needs it to validate facet codes."
        )
    data = c.load_yaml_file(path)
    if not isinstance(data, dict):
        raise c.CheckError("the " + label + " facet file is not a mapping: " + path)
    items = None
    for key in list_keys:
        value = data.get(key)
        if isinstance(value, list):
            items = value
            break
    if items is None:
        raise c.CheckError(
            "the " + label + " facet file " + path + " has no code list under any of "
            + ", ".join(list_keys)
        )
    codes = set()
    for item in items:
        if isinstance(item, dict):
            code = item.get("code")
        else:
            code = item
        if not isinstance(code, str) or not code:
            raise c.CheckError(
                "the " + label + " facet file " + path
                + " has an entry with a missing or non-string code: " + repr(item)
            )
        if code in codes:
            raise c.CheckError(
                "the " + label + " facet file " + path
                + " declares the code " + repr(code) + " more than once"
            )
        codes.add(code)
    if not codes:
        raise c.CheckError("the " + label + " facet file " + path + " declares no codes")
    return codes


# ---------------------------------------------------------------------------
# (a) internal entry facet membership
# ---------------------------------------------------------------------------

def _check_internal_facets(root, industry_codes, cluster_codes):
    entries = c.load_entries(root)
    faceted = 0
    for path, record in entries:
        entry_id = record.get("id", "(missing id)")
        subject = "entry " + entry_id + " [" + path + "]"

        industries = record.get("industry")
        if industries is not None:
            if not isinstance(industries, list):
                raise c.CheckError(subject + ": industry must be an array of codes")
            for code in industries:
                if code not in industry_codes:
                    raise c.CheckError(
                        subject + ": industry code " + repr(code)
                        + " is not defined in " + _rel(INDUSTRY_FACET)
                        + " (known codes: " + str(len(industry_codes)) + ")"
                    )

        clusters = record.get("cluster")
        if clusters is not None:
            if not isinstance(clusters, list):
                raise c.CheckError(subject + ": cluster must be an array of codes")
            for code in clusters:
                if code not in cluster_codes:
                    raise c.CheckError(
                        subject + ": cluster code " + repr(code)
                        + " is not defined in " + _rel(CLUSTER_FACET)
                        + " (known codes: " + str(len(cluster_codes)) + ")"
                    )

        if industries or clusters:
            faceted += 1

    c.ok(
        "internal facet membership: " + str(len(entries)) + " entries, "
        + str(faceted) + " carry facets, every present code is a known code"
    )
    return len(entries)


# ---------------------------------------------------------------------------
# (b) group map coverage
# ---------------------------------------------------------------------------

def _check_group_map(root, industry_codes):
    source_path = _abspath(root, EXTERNAL_SOURCE)
    map_path = _abspath(root, GROUP_MAP)

    _source_fields, source_rows = _read_csv(source_path, "external source catalogue")
    if not source_rows:
        raise c.CheckError("external source catalogue has no rows: " + source_path)
    source_groups = set()
    for index, row in enumerate(source_rows):
        group = row.get(GROUP_COLUMN)
        if group is None or group == "":
            raise c.CheckError(
                "external source row " + str(index) + " in " + source_path
                + " has an empty " + GROUP_COLUMN + " column"
            )
        source_groups.add(group)

    map_fields, map_rows = _read_csv(map_path, "group-industry map")
    if MAP_GROUP_COLUMN not in (map_fields or []) or MAP_INDUSTRIES_COLUMN not in (map_fields or []):
        raise c.CheckError(
            "group-industry map " + map_path + " must have columns "
            + MAP_GROUP_COLUMN + " and " + MAP_INDUSTRIES_COLUMN
            + "; found " + repr(map_fields)
        )
    map_groups = set()
    for index, row in enumerate(map_rows):
        group = row.get(MAP_GROUP_COLUMN)
        if group is None or group == "":
            raise c.CheckError(
                "group-industry map row " + str(index) + " in " + map_path
                + " has an empty " + MAP_GROUP_COLUMN + " column"
            )
        if group in map_groups:
            raise c.CheckError(
                "group-industry map " + map_path + " maps the Group " + repr(group)
                + " more than once"
            )
        map_groups.add(group)
        codes = _split_codes(row.get(MAP_INDUSTRIES_COLUMN))
        if not codes:
            raise c.CheckError(
                "group-industry map " + map_path + " maps the Group " + repr(group)
                + " to no industry code"
            )
        for code in codes:
            if code not in industry_codes:
                raise c.CheckError(
                    "group-industry map " + map_path + " maps the Group " + repr(group)
                    + " to industry code " + repr(code) + " which is not defined in "
                    + _rel(INDUSTRY_FACET)
                )

    missing = sorted(source_groups - map_groups)
    extra = sorted(map_groups - source_groups)
    if missing or extra:
        parts = ["group-industry map " + map_path + " does not cover the source Groups exactly:"]
        if missing:
            parts.append("    missing (in source, not mapped): " + repr(missing))
        if extra:
            parts.append("    extra (mapped, not in source): " + repr(extra))
        raise c.CheckError("\n".join(parts))

    c.ok(
        "group map coverage: " + str(len(map_groups)) + " Groups map exactly onto the "
        + str(len(source_groups)) + " source Groups, every mapped code known"
    )
    return len(map_groups)


# ---------------------------------------------------------------------------
# (c) and (e) generated-artifact regeneration guards
# ---------------------------------------------------------------------------

def _first_diff_line(committed_bytes, regenerated_bytes):
    exp = committed_bytes.decode("utf-8", "replace").splitlines()
    got = regenerated_bytes.decode("utf-8", "replace").splitlines()
    limit = min(len(exp), len(got))
    for i in range(limit):
        if exp[i] != got[i]:
            return i + 1, exp[i], got[i]
    if len(exp) != len(got):
        line = limit + 1
        exp_line = exp[limit] if limit < len(exp) else "(end of file)"
        got_line = got[limit] if limit < len(got) else "(end of file)"
        return line, exp_line, got_line
    return None, None, None


def _regenerate_and_compare(root, tool_segments, artifact_segments, label):
    """Regenerate one artifact inside a throwaway copy and byte-compare.

    Proves the committed artifact is current: run the generator against a copy of
    the tree (it auto-locates that copy as its root and writes the artifact to the
    committed path there), then assert the freshly written bytes equal the bytes
    committed in the real tree. The real tree is read only; only the copy is
    written. A failure names the first differing line.
    """
    committed_path = _abspath(root, artifact_segments)
    if not os.path.isfile(committed_path):
        raise c.CheckError(
            "the committed " + label + " is missing: " + committed_path
            + ". It is generated by " + _rel(tool_segments) + " and must be committed."
        )
    committed_bytes = _read_bytes(committed_path)

    temp_parent = tempfile.mkdtemp(prefix="elmm-facets-")
    temp_root = os.path.join(temp_parent, "registry")
    try:
        shutil.copytree(root, temp_root)

        tool_path = os.path.join(temp_root, *tool_segments)
        if not os.path.isfile(tool_path):
            raise c.CheckError(
                "the generator " + _rel(tool_segments) + " was not found, so the "
                + label + " freshness cannot be proven: " + tool_path
            )

        # Remove the artifact from the copy first, so a passing comparison proves
        # the generator actually wrote it rather than that it was left in place.
        temp_artifact = os.path.join(temp_root, *artifact_segments)
        if os.path.isfile(temp_artifact):
            os.remove(temp_artifact)

        proc = subprocess.run(
            [sys.executable, tool_path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=temp_root,
        )
        if proc.returncode != 0:
            detail = proc.stderr.decode("utf-8", "replace").strip() \
                or proc.stdout.decode("utf-8", "replace").strip() or "(no output)"
            raise c.CheckError(
                "the generator " + _rel(tool_segments) + " exited " + str(proc.returncode)
                + " while regenerating the " + label + ":\n" + detail
            )
        if not os.path.isfile(temp_artifact):
            raise c.CheckError(
                "the generator " + _rel(tool_segments) + " ran but did not write "
                + _rel(artifact_segments) + "; cannot prove the " + label + " is current"
            )

        regenerated_bytes = _read_bytes(temp_artifact)
        if regenerated_bytes != committed_bytes:
            lineno, exp_line, got_line = _first_diff_line(committed_bytes, regenerated_bytes)
            lines = [
                "the committed " + label + " is stale: re-running " + _rel(tool_segments)
                + " on the committed inputs produced different bytes.",
                "    committed: " + committed_path + " (" + str(len(committed_bytes)) + " bytes)",
                "    regenerated: " + str(len(regenerated_bytes)) + " bytes",
            ]
            if lineno is not None:
                lines.append("    first difference at line " + str(lineno) + ":")
                lines.append("      committed:   " + exp_line)
                lines.append("      regenerated: " + got_line)
            lines.append("    Regenerate and commit: python " + _rel(tool_segments))
            raise c.CheckError("\n".join(lines))
    finally:
        shutil.rmtree(temp_parent, ignore_errors=True)


# ---------------------------------------------------------------------------
# (d) external row validity
# ---------------------------------------------------------------------------

def _project_external_row(row, subject):
    """Project one raw CSV row onto the schema's lower_snake_case object shape.

    Applies the fixed header-to-key map (EXTERNAL_COLUMN_TO_KEY) so the object
    validates against external-standard.schema.json, which is
    additionalProperties:false over the snake keys. Industry and Cluster become
    arrays; every other cell stays a string. An unmapped column is a contract
    drift between the importer and CI, reported precisely rather than dropped.
    """
    obj = {}
    for column, value in row.items():
        if column is None:
            continue
        key = EXTERNAL_COLUMN_TO_KEY.get(column)
        if key is None:
            raise c.CheckError(
                subject + " has an unexpected column " + repr(column)
                + " that check_facets does not know how to project; the importer and"
                + " ci/check_facets.py column maps have drifted apart"
            )
        if key in EXTERNAL_ARRAY_KEYS:
            obj[key] = _split_codes(value)
        else:
            obj[key] = value if value is not None else ""
    return obj


def _check_external_rows(root, industry_codes):
    path = _abspath(root, EXTERNAL_STANDARDS)
    fields, rows = _read_csv(path, "external standards catalogue")
    if not rows:
        raise c.CheckError("external standards catalogue has no rows: " + path)
    if ROW_INDUSTRY_COLUMN not in (fields or []):
        raise c.CheckError(
            "external standards catalogue " + path + " has no " + ROW_INDUSTRY_COLUMN
            + " column; the import must add it. Found columns: " + repr(fields)
        )

    store, by_name = c.load_schema_store(root)
    ext_schema = by_name.get(EXTERNAL_SCHEMA_NAME)
    if ext_schema is None:
        raise c.CheckError(
            "the external standard schema " + EXTERNAL_SCHEMA_NAME
            + " was not found under the schema directory; check (d) needs it"
        )

    from jsonschema import Draft202012Validator
    try:
        Draft202012Validator.check_schema(ext_schema)
    except Exception as exc:
        raise c.CheckError(
            EXTERNAL_SCHEMA_NAME + " is not a valid Draft 2020-12 schema: " + str(exc)
        )

    try:
        validator = c.make_validator(ext_schema, store)
    except Exception as exc:
        raise c.CheckError(
            "could not build a validator for " + EXTERNAL_SCHEMA_NAME + ": " + str(exc)
        )

    for index, row in enumerate(rows):
        subject = "external standards row " + str(index)
        acronym = row.get("Acronym") or row.get("Name")
        if acronym:
            subject += " (" + str(acronym) + ")"

        obj = _project_external_row(row, subject)
        errors = sorted(validator.iter_errors(obj), key=lambda e: list(e.absolute_path))
        if errors:
            parts = [subject + " is invalid against " + EXTERNAL_SCHEMA_NAME + ":"]
            for error in errors[:10]:
                where = "/".join(str(p) for p in error.absolute_path) or "(root)"
                parts.append("    at " + where + ": " + error.message)
            if len(errors) > 10:
                parts.append("    ... and " + str(len(errors) - 10) + " more")
            raise c.CheckError("\n".join(parts))

        codes = obj.get("industry") or []
        if not codes:
            raise c.CheckError(
                subject + " has an empty " + ROW_INDUSTRY_COLUMN
                + " column; every external standard inherits at least one industry"
                + " from its Group"
            )
        for code in codes:
            if code not in industry_codes:
                raise c.CheckError(
                    subject + " carries industry code " + repr(code)
                    + " which is not defined in " + _rel(INDUSTRY_FACET)
                )

    c.ok(
        "external row validity: " + str(len(rows)) + " rows valid against "
        + EXTERNAL_SCHEMA_NAME + ", every Industry code known"
    )
    return len(rows)


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def run(root):
    c.info("check_facets: facet vocabulary and generated-artifact integrity")
    c.info("  root: " + root)

    industry_codes = _load_code_set(root, INDUSTRY_FACET, ("industries",), "industry")
    cluster_codes = _load_code_set(root, CLUSTER_FACET, ("clusters",), "cluster")
    c.ok(
        "facet vocabularies loaded: " + str(len(industry_codes)) + " industry codes, "
        + str(len(cluster_codes)) + " cluster codes"
    )

    # (a) internal entry facet membership
    entry_count = _check_internal_facets(root, industry_codes, cluster_codes)
    # (b) group map covers the source Groups exactly, every mapped code known
    group_count = _check_group_map(root, industry_codes)
    # (c) the committed external standards catalogue is a current import
    _regenerate_and_compare(root, IMPORT_TOOL, EXTERNAL_STANDARDS, "external standards catalogue")
    c.ok("import drift guard: external/external-standards.csv matches a fresh import")
    # (d) every external row validates and its Industry codes are known
    row_count = _check_external_rows(root, industry_codes)
    # (e) the committed unified index is a current build
    _regenerate_and_compare(root, BUILD_INDEX_TOOL, UNIFIED_INDEX, "unified index")
    c.ok("index freshness guard: index/unified-index.json matches a fresh build")

    c.info(
        "check_facets: PASS (" + str(entry_count) + " internal entries, "
        + str(group_count) + " groups, " + str(row_count) + " external rows)"
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description="Vercy registry facet and generated-artifact check")
    parser.add_argument("--root", default=None, help="registry root directory")
    args = parser.parse_args(argv)
    try:
        run(c.registry_root(args.root))
        return 0
    except c.CheckError as exc:
        sys.stderr.write("check_facets: FAIL\n" + str(exc) + "\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
