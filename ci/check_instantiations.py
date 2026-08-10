#!/usr/bin/env python3
"""check_instantiations: the B6 external-to-internal transform admission check.

The sixth admission check. B6 is the flagship transform: it takes ONE external
standard from external/external-standards.csv and instantiates an internal
tenant meta-model from it, overlaying the ver.cy governance (policies,
regulations, rules) and recording full lineage back to the external source. The
formula (owner): external-to-internal = Extension-Model + Policy-Consistency +
Data-Mastership, made one operation. It composes ARCH-014 (Policy-Consistency),
ARCH-016 (Meta-Model-Composition), ARCH-018 (Data-Mastership),
Extension-Model, and Provenance-Graph, under the Common Operating Law invariant
controls IC-1 to IC-8 and the delegation tiers T1 to T3.

Every transform run leaves two committed artifacts: a new internal Model
Registration Record (an MMDG node under entries/, picked up by build_index) and
an instantiation manifest under instantiations/ that records exactly how the
external model was bound, which policies were overlaid, who masters the data,
and the lineage. This check guards those artifacts. It is a no-op that passes
with a note until the first instantiation is committed, so the transform can be
built and shipped incrementally without breaking the gate.

The check guards both directions of the entry / manifest coupling. Forward
(manifest -> entry), for every file in instantiations/*.manifest.json:

  (a) SCHEMA. The manifest validates against
      schema/instantiation-manifest.schema.json.

  (b) INTERNAL ENTRY. manifest.internal_id names an entry file
      entries/<internal_id>.yaml that exists, validates against the registry
      node profile schema (registry-node.schema.json, v0.3), and carries the
      new v0.3 provenance fields tenant, derived_from and external_binding.

  (c) EXTERNAL RESOLUTION. manifest.external_ref.registry_ref resolves to a real
      row in external/external-standards.csv, matched by Acronym or Name. The
      instantiated model is mirrored-external data per IC-3, never a command, so
      its source must be a real catalogued standard.

  (d) POLICY OVERLAY. Every applied_policies id exists in the cited profile
      transform/policy-profiles/<profile>.yaml (ARCH-014 Policy-Consistency:
      the overlay is closed over the profile it names).

  (e) INDUSTRY INHERITANCE. The internal entry's industry facet equals the
      external row's Industry verbatim (the transform inherits the facet, it
      does not invent one).

  (f) IC-1 MASTERSHIP. manifest.mastership.system_of_record is the external
      source, not the tenant. Mastership is declared never inferred (ARCH-018),
      one master per dataset (IC-1): the external standard masters the mirrored
      data, the tenant does not.

Reverse (entry -> manifest), so an instantiated entry cannot escape the forward
checks by simply having no manifest:

  (r) BACKED. Every entry under entries/ that carries the B6 transform signature
      (a non-empty derived_from or external_binding) is claimed by exactly one
      committed manifest whose internal_id names it. A hand-authored or drifted
      entry that looks instantiated but has no manifest fails closed, rather
      than passing on check_schema alone with zero external resolution, policy
      overlay, IC-1 mastership or replay coverage. This runs even when zero
      manifests are committed, so the vacuous-pass path cannot hide such an
      entry.

And, over every committed pair:

  (g) DETERMINISM (replayability). Re-running tools/instantiate.py for the same
      (external, tenant, profile, created_at) into a throwaway copy of the tree
      reproduces the committed entry and manifest byte for byte. The transform
      is a pure function of its inputs (ELMM-I23: no wall clock, no random; the
      timestamp is the manifest created_at passed through --at), so the button
      is replayable and the committed fixtures are exactly what it emits.

Determinism contract for tools/instantiate.py (shared with the check_facets /
check_zero_change generator idiom): the tool locates the registry root from its
own file location and, given

    python tools/instantiate.py --external <registry_ref> \
        --tenant <tenant> --profile <profile> --at <created_at>

writes entries/<internal_id>.yaml and instantiations/<instantiation_id>.manifest.json
under that root, deterministically. check_instantiations runs it inside a
temporary copy of the tree (after deleting the committed entry and manifest from
the copy, so a passing comparison proves the tool wrote them) and byte-compares
what it wrote against the committed fixtures in the real tree. The real tree is
read only.

Exits non-zero with a precise message on the first violation. Follows the
existing "ok" line style. The root defaults to the parent of this script's
directory, so the check is working directory independent and reusable on a
copied tree.

Usage:
    python check_instantiations.py [--root <registry-root>]
"""

import argparse
import csv
import glob
import os
import shutil
import subprocess
import sys

import _common as c


# Repo-relative locations, as path segment tuples so they join on any platform.
INSTANTIATIONS_DIR = ("instantiations",)
ENTRIES_DIR = ("entries",)
EXTERNAL_STANDARDS = ("external", "external-standards.csv")
POLICY_PROFILE_DIR = ("transform", "policy-profiles")
INSTANTIATE_TOOL = ("tools", "instantiate.py")

MANIFEST_GLOB = "*.manifest.json"
ENTRY_GLOB = "*.yaml"
MANIFEST_SCHEMA_NAME = "instantiation-manifest.schema.json"

# The entry fields that mark an entry as a B6 instantiation (the v0.3 transform
# signature). Any one of them, present and non-empty, means the entry must be
# backed by a committed instantiation manifest.
B6_SIGNATURE_FIELDS = ("derived_from", "external_binding")

# External catalogue columns the check reads by name.
CSV_ACRONYM = "Acronym"
CSV_NAME = "Name"
CSV_SOURCE_URL = "SpecificationSourceURL"
CSV_NAMESPACE = "NamespaceURI"
CSV_INDUSTRY = "Industry"


# ---------------------------------------------------------------------------
# Small readers (kept local so _common and the existing checks are untouched)
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

    utf-8-sig so a stray byte order mark does not corrupt the first column name,
    newline="" so the csv module owns line handling. Mirrors check_facts.
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
    """Split a semicolon-separated code cell into a stable list, dropping blanks."""
    if cell is None:
        return []
    return [part.strip() for part in cell.split(";") if part.strip()]


def _policy_id(item):
    """Extract a policy id from an applied_policies element (str or {id: ...})."""
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        value = item.get("id")
        if isinstance(value, str):
            return value
    return None


def _is_policy_container_key(key):
    lowered = str(key).lower()
    return "polic" in lowered or "control" in lowered


def _collect_profile_policy_ids(node, parent_key, out):
    """Recursively collect every policy identifier declared in a profile document.

    A profile enumerates its overlay as the eight invariant controls IC-1..IC-8
    plus the profile-local policies, and it may encode each as a mapping with an
    id field or as a bare string under a policies/controls list. This collector
    accepts either shape: every mapping's string id is collected, and every bare
    string element of a list whose key mentions policy or control is collected.
    """
    if isinstance(node, dict):
        ident = node.get("id")
        if isinstance(ident, str) and ident:
            out.add(ident)
        for key, value in node.items():
            _collect_profile_policy_ids(value, key, out)
    elif isinstance(node, list):
        for item in node:
            if isinstance(item, str):
                if parent_key is not None and _is_policy_container_key(parent_key) and item:
                    out.add(item)
            else:
                _collect_profile_policy_ids(item, parent_key, out)


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


# ---------------------------------------------------------------------------
# B6 signature scan over entries/ (reverse-direction guard)
# ---------------------------------------------------------------------------

def _has_b6_signature(entry):
    """True if the entry carries the v0.3 transform signature (an instantiation).

    Any one of the B6 signature fields, present and non-empty, marks the entry as
    the product of the external-to-internal transform. Such an entry must be
    backed by a committed manifest.
    """
    for field in B6_SIGNATURE_FIELDS:
        value = entry.get(field)
        if value not in (None, "", [], {}):
            return True
    return False


def _scan_instantiated_entries(root):
    """Return [(internal_id, entry_path), ...] for every entry with the signature.

    Malformed or non-mapping entries are check_schema's to report, not this
    guard's, so they are skipped here rather than raised on. The list is sorted
    for a stable, deterministic report.
    """
    entries_dir = _abspath(root, ENTRIES_DIR)
    found = []
    if not os.path.isdir(entries_dir):
        return found
    for path in sorted(glob.glob(os.path.join(entries_dir, ENTRY_GLOB))):
        try:
            entry = c.load_yaml_file(path)
        except Exception:
            # A malformed entry is check_schema's failure, not this guard's.
            continue
        if not isinstance(entry, dict):
            continue
        if not _has_b6_signature(entry):
            continue
        ident = entry.get("id")
        if not isinstance(ident, str) or not ident:
            ident = os.path.splitext(os.path.basename(path))[0]
        found.append((ident, path))
    found.sort()
    return found


def _assert_entries_have_manifests(instantiated_entries, records, root):
    """Reverse guard: every instantiated entry is backed by exactly one manifest.

    The forward per-manifest path proves manifest -> entry; this proves the
    converse, so a hand-authored or drifted entry that carries the B6 signature
    but has no manifest fails closed instead of passing on check_schema alone.
    Called even when zero manifests are committed (records empty), so the
    vacuous-pass path cannot hide such an entry.
    """
    by_internal = {}
    for rec in records:
        by_internal.setdefault(rec["internal_id"], []).append(rec)
    for internal_id, entry_path in instantiated_entries:
        rel_entry = os.path.relpath(entry_path, root).replace(os.sep, "/")
        recs = by_internal.get(internal_id, [])
        if not recs:
            raise c.CheckError(
                "instantiated entry " + rel_entry + " carries the B6 transform"
                + " signature (a non-empty derived_from or external_binding) but no"
                + " committed manifest in " + _rel(INSTANTIATIONS_DIR)
                + "/ declares internal_id " + repr(internal_id)
                + "; every instantiated entry must be backed by an instantiation"
                + " manifest, else it bypasses external resolution, policy overlay,"
                + " IC-1 mastership and the determinism replay (B6 provenance)"
            )
        if len(recs) > 1:
            manifests = sorted(rec["rel"] for rec in recs)
            raise c.CheckError(
                "instantiated entry " + rel_entry + " (internal_id "
                + repr(internal_id) + ") is claimed by more than one manifest: "
                + ", ".join(manifests)
                + "; exactly one manifest may master an instantiated entry"
            )
    if instantiated_entries:
        count = len(instantiated_entries)
        c.ok(
            "reverse guard: all " + str(count) + " instantiated entr"
            + ("y is" if count == 1 else "ies are")
            + " backed by exactly one manifest"
        )


# ---------------------------------------------------------------------------
# External catalogue index (registry_ref -> row, by Acronym or Name)
# ---------------------------------------------------------------------------

def _load_external_index(root):
    path = _abspath(root, EXTERNAL_STANDARDS)
    fields, rows = _read_csv(path, "external standards catalogue")
    for column in (CSV_ACRONYM, CSV_NAME, CSV_INDUSTRY):
        if column not in (fields or []):
            raise c.CheckError(
                "external standards catalogue " + path + " has no " + column
                + " column; found " + repr(fields)
            )
    by_acronym = {}
    by_name = {}
    for row in rows:
        acronym = (row.get(CSV_ACRONYM) or "").strip()
        name = (row.get(CSV_NAME) or "").strip()
        if acronym:
            by_acronym.setdefault(acronym, row)
        if name:
            by_name.setdefault(name, row)
    return path, by_acronym, by_name


def _resolve_external(registry_ref, by_acronym, by_name, subject, csv_path):
    ref = (registry_ref or "").strip()
    if not ref:
        raise c.CheckError(subject + ": external_ref.registry_ref is empty")
    row = by_acronym.get(ref)
    if row is None:
        row = by_name.get(ref)
    if row is None:
        raise c.CheckError(
            subject + ": external_ref.registry_ref " + repr(ref)
            + " resolves to no row in " + csv_path
            + " (matched by " + CSV_ACRONYM + " or " + CSV_NAME + ")"
        )
    return row


# ---------------------------------------------------------------------------
# Per-manifest assertions (a) to (f)
# ---------------------------------------------------------------------------

def _require_string(mapping, key, subject):
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise c.CheckError(subject + ": " + key + " is missing or not a non-empty string")
    return value


def _check_one_manifest(root, manifest_path, manifest, store, manifest_schema,
                        node_schema, by_acronym, by_name, csv_path):
    rel = os.path.relpath(manifest_path, root).replace(os.sep, "/")
    subject = "manifest " + rel

    # (a) the manifest validates against the manifest schema.
    c.validate_or_raise(
        manifest_schema, manifest, store, subject, MANIFEST_SCHEMA_NAME
    )

    tenant = _require_string(manifest, "tenant", subject)
    profile = _require_string(manifest, "profile", subject)
    internal_id = _require_string(manifest, "internal_id", subject)
    created_at = _require_string(manifest, "created_at", subject)

    external_ref = manifest.get("external_ref")
    if not isinstance(external_ref, dict):
        raise c.CheckError(subject + ": external_ref is missing or not an object")
    registry_ref = _require_string(external_ref, "registry_ref", subject + " external_ref")

    # (b) internal_id names an entry that exists, validates, and carries the
    # v0.3 provenance fields.
    entry_path = _abspath(root, ENTRIES_DIR + (internal_id + ".yaml",))
    if not os.path.isfile(entry_path):
        raise c.CheckError(
            subject + ": internal_id " + repr(internal_id)
            + " names no entry file " + _rel(ENTRIES_DIR) + "/" + internal_id + ".yaml"
        )
    entry = c.load_yaml_file(entry_path)
    if not isinstance(entry, dict):
        raise c.CheckError("instantiated entry is not a mapping: " + entry_path)
    entry_subject = "instantiated entry " + internal_id + " [" + entry_path + "]"
    c.validate_or_raise(node_schema, entry, store, entry_subject, "registry-node schema")
    if entry.get("id") != internal_id:
        raise c.CheckError(
            entry_subject + ": entry id " + repr(entry.get("id"))
            + " does not equal the manifest internal_id " + repr(internal_id)
        )
    for field in ("tenant", "derived_from", "external_binding"):
        if field not in entry or entry.get(field) in (None, "", [], {}):
            raise c.CheckError(
                entry_subject + ": the v0.3 provenance field " + repr(field)
                + " is missing or empty; an instantiated entry must carry it"
            )

    # (b') semantic_package, when present, names the imported EXTERNAL package
    # (Extension-Model: the standard and its external version), never the fresh
    # internal model. internal_id@version is the misattribution the grounding
    # review flagged; fail closed on it so the Extension-Model leg of the owner's
    # formula is not inverted.
    binding = entry.get("external_binding")
    if isinstance(binding, dict):
        package = binding.get("semantic_package")
        if isinstance(package, str) and package:
            internal_package = internal_id + "@" + str(entry.get("version"))
            if package == internal_package:
                raise c.CheckError(
                    entry_subject + ": external_binding.semantic_package "
                    + repr(package) + " names the internal model; it must name the"
                    + " imported external Semantic Package (Extension-Model: the"
                    + " external standard and its external version), not"
                    + " internal_id@version"
                )

    # (c) the external reference resolves to a real catalogued standard.
    row = _resolve_external(registry_ref, by_acronym, by_name, subject, csv_path)

    # (d) every overlaid policy exists in the cited profile.
    profile_path = _abspath(root, POLICY_PROFILE_DIR + (profile + ".yaml",))
    if not os.path.isfile(profile_path):
        raise c.CheckError(
            subject + ": profile " + repr(profile) + " names no policy profile "
            + _rel(POLICY_PROFILE_DIR) + "/" + profile + ".yaml"
        )
    profile_doc = c.load_yaml_file(profile_path)
    if not isinstance(profile_doc, dict):
        raise c.CheckError("policy profile is not a mapping: " + profile_path)
    declared_ids = set()
    _collect_profile_policy_ids(profile_doc, None, declared_ids)
    applied = manifest.get("applied_policies")
    if not isinstance(applied, list) or not applied:
        raise c.CheckError(subject + ": applied_policies is missing or empty")
    for item in applied:
        pid = _policy_id(item)
        if pid is None:
            raise c.CheckError(
                subject + ": applied_policies has an element with no policy id: "
                + repr(item)
            )
        if pid not in declared_ids:
            raise c.CheckError(
                subject + ": applied policy " + repr(pid)
                + " is not declared in the cited profile "
                + _rel(POLICY_PROFILE_DIR) + "/" + profile + ".yaml"
            )

    # (e) the entry industry facet equals the external row's Industry verbatim.
    external_industry = _split_codes(row.get(CSV_INDUSTRY))
    entry_industry = entry.get("industry")
    if not isinstance(entry_industry, list):
        raise c.CheckError(
            entry_subject + ": industry must be an array of codes inherited from the"
            + " external standard, found " + repr(entry_industry)
        )
    if entry_industry != external_industry:
        raise c.CheckError(
            subject + ": the instantiated entry industry " + repr(entry_industry)
            + " does not equal the external row Industry " + repr(external_industry)
            + " (the transform inherits the facet verbatim)"
        )

    # (f) IC-1: the master is the external source, not the tenant.
    mastership = manifest.get("mastership")
    if not isinstance(mastership, dict):
        raise c.CheckError(subject + ": mastership is missing or not an object")
    system_of_record = _require_string(mastership, "system_of_record", subject + " mastership")
    if system_of_record == tenant:
        raise c.CheckError(
            subject + ": IC-1 violation, mastership.system_of_record equals the tenant "
            + repr(tenant) + "; the external source masters mirrored-external data,"
            + " not the tenant (ARCH-018, mastership declared never inferred)"
        )
    external_identities = set(
        value for value in (
            registry_ref,
            external_ref.get("name"),
            external_ref.get("source_url"),
            (row.get(CSV_ACRONYM) or "").strip(),
            (row.get(CSV_NAME) or "").strip(),
            (row.get(CSV_SOURCE_URL) or "").strip(),
            (row.get(CSV_NAMESPACE) or "").strip(),
        )
        if isinstance(value, str) and value
    )
    if system_of_record not in external_identities:
        raise c.CheckError(
            subject + ": IC-1 violation, mastership.system_of_record "
            + repr(system_of_record) + " is not the external source; expected one of "
            + repr(sorted(external_identities))
        )

    c.ok(
        rel + ": valid, entry " + internal_id + " bound to external "
        + registry_ref + ", " + str(len(applied)) + " policies overlaid, mastered by "
        + system_of_record
    )
    return {
        "manifest_path": manifest_path,
        "rel": rel,
        "internal_id": internal_id,
        "entry_path": entry_path,
        "tenant": tenant,
        "profile": profile,
        "created_at": created_at,
        "registry_ref": registry_ref,
    }


# ---------------------------------------------------------------------------
# (g) determinism / replayability
# ---------------------------------------------------------------------------

def _check_determinism(root, records):
    """Re-run the transform inside a throwaway copy and byte-compare artifacts.

    Proves each committed (entry, manifest) pair is exactly what
    tools/instantiate.py emits for the manifest's own (external, tenant, profile,
    created_at). The tool auto-locates the copy as its root and writes to the
    committed relative paths; the committed pair is deleted from the copy first,
    so a passing comparison proves the tool wrote them. The real tree is read
    only.
    """
    import tempfile

    tool_rel = _rel(INSTANTIATE_TOOL)
    if not os.path.isfile(_abspath(root, INSTANTIATE_TOOL)):
        raise c.CheckError(
            "the transform tool " + tool_rel + " was not found, so replayability of "
            + str(len(records)) + " instantiation(s) cannot be proven: "
            + _abspath(root, INSTANTIATE_TOOL)
        )

    temp_parent = tempfile.mkdtemp(prefix="elmm-instantiate-")
    temp_root = os.path.join(temp_parent, "registry")
    try:
        shutil.copytree(root, temp_root)
        tool_path = os.path.join(temp_root, *INSTANTIATE_TOOL)
        for rec in records:
            entry_rel = os.path.relpath(rec["entry_path"], root).replace(os.sep, "/")
            manifest_rel = rec["rel"]
            committed_entry = _read_bytes(rec["entry_path"])
            committed_manifest = _read_bytes(rec["manifest_path"])

            # Delete the committed pair from the copy so a match proves a write.
            for rel_path in (entry_rel, manifest_rel):
                temp_file = os.path.join(temp_root, *rel_path.split("/"))
                if os.path.isfile(temp_file):
                    os.remove(temp_file)

            command = [
                sys.executable, tool_path,
                "--external", rec["registry_ref"],
                "--tenant", rec["tenant"],
                "--profile", rec["profile"],
                "--at", rec["created_at"],
            ]
            proc = subprocess.run(
                command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=temp_root
            )
            if proc.returncode != 0:
                detail = proc.stderr.decode("utf-8", "replace").strip() \
                    or proc.stdout.decode("utf-8", "replace").strip() or "(no output)"
                raise c.CheckError(
                    "replaying " + tool_rel + " for " + manifest_rel + " exited "
                    + str(proc.returncode) + ":\n" + detail
                )

            for rel_path, committed_bytes, label in (
                (entry_rel, committed_entry, "instantiated entry"),
                (manifest_rel, committed_manifest, "instantiation manifest"),
            ):
                temp_file = os.path.join(temp_root, *rel_path.split("/"))
                if not os.path.isfile(temp_file):
                    raise c.CheckError(
                        "replaying " + tool_rel + " for " + manifest_rel
                        + " did not write the " + label + " " + rel_path
                        + "; the transform is not replayable to the committed path"
                    )
                regenerated = _read_bytes(temp_file)
                if regenerated != committed_bytes:
                    lineno, exp_line, got_line = _first_diff_line(committed_bytes, regenerated)
                    lines = [
                        "the committed " + label + " " + rel_path + " is not replayable:"
                        + " re-running " + tool_rel + " with the manifest inputs produced"
                        + " different bytes.",
                        "    committed: " + str(len(committed_bytes)) + " bytes",
                        "    replayed:  " + str(len(regenerated)) + " bytes",
                    ]
                    if lineno is not None:
                        lines.append("    first difference at line " + str(lineno) + ":")
                        lines.append("      committed: " + exp_line)
                        lines.append("      replayed:  " + got_line)
                    raise c.CheckError("\n".join(lines))
    finally:
        shutil.rmtree(temp_parent, ignore_errors=True)

    c.ok(
        "determinism: " + str(len(records))
        + " instantiation(s) replay byte-identical from tools/instantiate.py"
    )


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def run(root):
    c.info("check_instantiations: B6 external-to-internal transform integrity")
    c.info("  root: " + root)

    # Reverse-direction inventory first (entry -> manifest). Computed before the
    # manifest glob so an entry carrying the B6 signature cannot slip through the
    # vacuous-pass path when no manifest is committed.
    instantiated_entries = _scan_instantiated_entries(root)

    inst_dir = _abspath(root, INSTANTIATIONS_DIR)
    manifest_paths = []
    if os.path.isdir(inst_dir):
        manifest_paths = sorted(glob.glob(os.path.join(inst_dir, MANIFEST_GLOB)))

    if not manifest_paths:
        # No manifests: still fail closed on any instantiated entry with no
        # manifest. With records empty, the reverse guard raises on the first
        # such entry; if there are none it is a no-op.
        _assert_entries_have_manifests(instantiated_entries, [], root)
        if not os.path.isdir(inst_dir):
            c.ok(
                "no " + _rel(INSTANTIATIONS_DIR) + "/ directory yet; the transform is"
                + " unused, nothing to guard (vacuously passes)"
            )
        else:
            c.ok(
                _rel(INSTANTIATIONS_DIR) + "/ has no " + MANIFEST_GLOB + " files; the"
                + " transform is unused, nothing to guard (vacuously passes)"
            )
        c.info("check_instantiations: PASS (0 instantiations)")
        return

    store, by_name = c.load_schema_store(root)
    manifest_schema = by_name.get(MANIFEST_SCHEMA_NAME)
    if manifest_schema is None:
        raise c.CheckError(
            "the instantiation manifest schema " + MANIFEST_SCHEMA_NAME
            + " was not found under the schema directory, but "
            + str(len(manifest_paths)) + " manifest(s) are committed"
        )
    from jsonschema import Draft202012Validator
    try:
        Draft202012Validator.check_schema(manifest_schema)
    except Exception as exc:
        raise c.CheckError(
            MANIFEST_SCHEMA_NAME + " is not a valid Draft 2020-12 schema: " + str(exc)
        )
    node_schema = c.pick_schema(by_name, c.NODE_SCHEMA_NAMES, "MMDG node profile")

    csv_path, by_acronym, by_name_row = _load_external_index(root)

    records = []
    for manifest_path in manifest_paths:
        manifest = c.load_json_file(manifest_path)
        if not isinstance(manifest, dict):
            raise c.CheckError(
                "instantiation manifest is not a JSON object: " + manifest_path
            )
        records.append(
            _check_one_manifest(
                root, manifest_path, manifest, store, manifest_schema,
                node_schema, by_acronym, by_name_row, csv_path,
            )
        )

    # (r) reverse guard: every instantiated entry is backed by exactly one of the
    # manifests just verified. Closes the manifest-driven-only gap.
    _assert_entries_have_manifests(instantiated_entries, records, root)

    # (g) replayability, across all manifests, one throwaway copy.
    _check_determinism(root, records)

    c.info("check_instantiations: PASS (" + str(len(records)) + " instantiations)")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Vercy registry B6 instantiation transform check"
    )
    parser.add_argument("--root", default=None, help="registry root directory")
    args = parser.parse_args(argv)
    try:
        run(c.registry_root(args.root))
        return 0
    except c.CheckError as exc:
        sys.stderr.write("check_instantiations: FAIL\n" + str(exc) + "\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
