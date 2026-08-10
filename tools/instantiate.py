#!/usr/bin/env python3
"""instantiate: the external-to-internal transform, the B6 button.

One deterministic operation that crosses the boundary the unified registry
draws. It takes ONE external standard from the discovery catalogue (a row of
external/external-standards.csv) and instantiates an INTERNAL tenant meta-model
from it: a new Model Registration Record that is a first-class MMDG node the
resolver can compose, plus an instantiation manifest that records exactly how
the crossing was made. Stated by the owner as a formula:

    external-to-internal = Extension-Model + Policy-Consistency + Data-Mastership

made a single operation. Extension-Model supplies the binding (adopt the
external model by reference, never by silent copy). Policy-Consistency (ARCH-014)
supplies the governance overlay: the policy profile's policies, including the
eight invariant controls IC-1 to IC-8 of the Common Operating Law. Data-Mastership
(ARCH-018) fixes who owns the data: the external source is the master, the
registry mirrors. The composition mechanism is ARCH-016 (Meta-Model-Composition),
the same roles R1 to R8 the facet layer carries. Lineage back to the source is
recorded per Provenance-Graph. The bound external content is mirrored-external
per IC-3: data, never instructions. A fresh instantiation starts at delegation
tier T1 (human-in-the-loop) per the Common Operating Law. Bind by reference to
those documents; nothing here restates them.

Determinism is mandatory (ELMM-I23). There is no wall-clock read (the timestamp
is the --at ISO-8601 argument) and no randomness: the internal id, the semantic
fingerprint and the instantiation id are deterministic hashes over canonical
content, key order is fixed, and both artifacts are emitted with a trailing
newline, so re-running the transform with the same inputs yields a byte-identical
entry and manifest. The tool locates the registry root from its own file
location (matching ci/_common.py), so it runs from any working directory and on
a copied tree.

Usage:
    python instantiate.py --external <ACRONYM-or-NAME> --tenant <name> --at <ISO8601>
                          [--profile vercy-baseline]
                          [--registry <root>] [--write]
                          [--out-entry <path>] [--out-manifest <path>] [--print]

The default output, given no --out-entry/--out-manifest/--print, writes the pair
into the registry: entries/<id>.yaml and instantiations/<id>.manifest.json, where
<id> is the new internal id. This is the mode ci/check_instantiations.py replays.

Runtime dependencies: Python 3 standard library plus PyYAML and jsonschema.
"""

import argparse
import csv
import hashlib
import json
import os
import re
import sys

try:
    import yaml
except ImportError as exc:  # pragma: no cover - environment guard
    sys.stderr.write("FAIL: PyYAML is required (pip install pyyaml): " + str(exc) + "\n")
    raise


# ---------------------------------------------------------------------------
# The mapping (normative in transform/EXTERNAL-TO-INTERNAL.md and here). The
# external standard's registry classification settles the binding: its
# DefaultLinkType drives the link_type and its CompositionalRole drives the
# composition_kind, per ARCH-016. The AISMM conditional then forces embed when
# the composition_kind resolves to value_object.
# ---------------------------------------------------------------------------

LINK_TYPE_MAP = {
    "EMBED": "embed",
    "REFERENCE": "reference",
    "MIX-IN": "mixin",
    "ALIGN": "align",
    "EXTEND": "extend",
    "COMPOSE": "reference",
    "N/A": "annotate",
}

COMPOSITION_KIND_MAP = {
    "R1": "value_object",
    "R2": "code",
    "R3": "code",
    "R4": "entity",
    "R5": "facet",
    "R6": "entity",
    "R7": "entity",
    "R8": "attribute",
}

INTERNAL_VERSION = "0.1.0"

# External catalogue columns read by name.
CSV_GROUP = "Group"
CSV_NAME = "Name"
CSV_ACRONYM = "Acronym"
CSV_SOURCE_URL = "SpecificationSourceURL"
CSV_MAINTAINER = "Maintainer"
CSV_NAMESPACE = "NamespaceURI"
CSV_YEAR = "Year"
CSV_ROLE = "CompositionalRole"
CSV_LINK = "DefaultLinkType"
CSV_INDUSTRY = "Industry"
CSV_LICENSE = "License"  # not in the current catalogue; used when present.

_SLUG_RE = re.compile(r"[^a-z0-9]+")
_TENANT_TOKEN_RE = re.compile(r"[^a-z0-9]+")

NODE_SCHEMA_NAMES = ("registry-node.schema.json", "mmdg-node.schema.json")
MANIFEST_SCHEMA_NAME = "instantiation-manifest.schema.json"


class TransformError(Exception):
    """A transform failure with a precise, human-readable diagnostic."""


def fail(message):
    raise TransformError(message)


def note(message):
    """Informational output on stderr, so stdout is reserved for --print."""
    sys.stderr.write(message + "\n")


# ---------------------------------------------------------------------------
# Root and slugging
# ---------------------------------------------------------------------------

def registry_root(explicit=None):
    if explicit:
        return os.path.abspath(explicit)
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(here, os.pardir))


def slugify(text):
    return _SLUG_RE.sub("-", (text or "").strip().lower()).strip("-")


def tenant_token(text):
    """Lower alphanumeric token for the id and namespace first segment.

    The registry id pattern forbids a hyphen in the first dot-segment, so the
    tenant token is stripped to [a-z0-9]. The raw --tenant string is kept for the
    tenant field and the steward, unchanged.
    """
    return _TENANT_TOKEN_RE.sub("", (text or "").strip().lower())


# ---------------------------------------------------------------------------
# Canonicalisation and hashing (deterministic, no wall clock, no random)
# ---------------------------------------------------------------------------

def canonical_json(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def first16hex(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# External catalogue: find the ONE matching row
# ---------------------------------------------------------------------------

def load_external_rows(root):
    path = os.path.join(root, "external", "external-standards.csv")
    if not os.path.isfile(path):
        fail(
            "external standards catalogue not found: " + path
            + " (run tools/import_external.py first)"
        )
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        for required in (CSV_NAME, CSV_ACRONYM, CSV_INDUSTRY):
            if required not in fields:
                fail(
                    "external standards catalogue " + path + " is missing the required column "
                    + repr(required) + "; found " + repr(fields)
                )
        rows = list(reader)
    return path, rows


def find_one(rows, query, csv_path):
    """Return the single row whose Acronym or Name matches query (case-insensitive
    exact). Error clearly on zero or more than one distinct match."""
    needle = (query or "").strip().lower()
    if not needle:
        fail("--external is empty; give an Acronym or Name from " + csv_path)
    hits = []
    for index, row in enumerate(rows):
        acronym = (row.get(CSV_ACRONYM) or "").strip()
        name = (row.get(CSV_NAME) or "").strip()
        if acronym.lower() == needle or name.lower() == needle:
            hits.append((index, row))
    if not hits:
        fail(
            "no external standard matches --external " + repr(query)
            + " by Acronym or Name (case-insensitive exact) in " + csv_path
        )
    if len(hits) > 1:
        labels = []
        for _index, row in hits:
            labels.append(
                (row.get(CSV_NAME) or "").strip()
                + " [" + (row.get(CSV_ACRONYM) or "").strip() + "]"
            )
        fail(
            "--external " + repr(query) + " is ambiguous: it matches "
            + str(len(hits)) + " rows in " + csv_path + " (" + "; ".join(labels)
            + "). Disambiguate with the exact Acronym or Name."
        )
    return hits[0][1]


# ---------------------------------------------------------------------------
# Policy profile
# ---------------------------------------------------------------------------

def load_profile(root, profile_id):
    path = os.path.join(root, "transform", "policy-profiles", profile_id + ".yaml")
    if not os.path.isfile(path):
        fail(
            "policy profile " + repr(profile_id) + " not found: " + path
            + " (expected transform/policy-profiles/" + profile_id + ".yaml)"
        )
    with open(path, "r", encoding="utf-8") as handle:
        doc = yaml.safe_load(handle)
    if not isinstance(doc, dict):
        fail("policy profile is not a mapping: " + path)

    # The ordered policy ids. Each 'policies' element is either a bare string id
    # or a mapping carrying an 'id'; both shapes are accepted so the profile can
    # document a rule and a source alongside each id. This ordered list is copied
    # verbatim into the entry's and the manifest's applied_policies.
    policies = doc.get("policies")
    if not isinstance(policies, list) or not policies:
        fail("policy profile " + path + " declares no non-empty 'policies' list")
    applied = []
    for item in policies:
        if isinstance(item, str) and item.strip():
            applied.append(item.strip())
        elif isinstance(item, dict) and isinstance(item.get("id"), str) and item.get("id").strip():
            applied.append(item["id"].strip())
        else:
            fail("policy profile " + path + " has a policy element with no id: " + repr(item))

    # Delegation tier default (T1 for a fresh instantiation). Accept either key.
    tier = str(doc.get("default_delegation_tier", doc.get("delegation_tier_default", "T1")))

    # Mastership stance. Accept either 'mastership_stance' or 'mastership'. The
    # actual system_of_record is derived from the external row (never this file);
    # only the flow direction, conflict rule and cadence are read here.
    mastership = doc.get("mastership_stance", doc.get("mastership")) or {}
    if not isinstance(mastership, dict):
        fail("policy profile " + path + " has a malformed mastership stanza")
    return {
        "applied_policies": applied,
        "delegation_tier": tier,
        "flow_direction": str(mastership.get("flow_direction", "inbound")),
        "conflict_rule": str(mastership.get("conflict_rule", "source-wins")),
        "cadence": str(mastership.get("cadence", "PT24H")),
    }


# ---------------------------------------------------------------------------
# Schema validation (offline, deterministic)
# ---------------------------------------------------------------------------

def load_schema_store(root):
    directory = os.path.join(root, "schema")
    if not os.path.isdir(directory):
        fail("schema directory not found: " + directory)
    store = {}
    by_name = {}
    for name in sorted(os.listdir(directory)):
        if not name.endswith(".json"):
            continue
        full = os.path.join(directory, name)
        try:
            with open(full, "r", encoding="utf-8") as handle:
                doc = json.load(handle)
        except json.JSONDecodeError as exc:
            fail("invalid JSON schema " + full + ": " + str(exc))
        if isinstance(doc, dict):
            schema_id = doc.get("$id")
            if schema_id:
                store[schema_id] = doc
            by_name.setdefault(name, doc)
    return store, by_name


def pick_schema(by_name, names, label):
    for candidate in names:
        if candidate in by_name:
            return by_name[candidate]
    fail(
        "could not find the " + label + " schema; looked for " + ", ".join(names)
        + " under the registry schema directory"
    )


def make_validator(schema, store):
    from jsonschema import Draft202012Validator
    try:
        from referencing import Registry, Resource
        resources = [(sid, Resource.from_contents(doc)) for sid, doc in store.items()]
        registry = Registry().with_resources(resources)
        return Draft202012Validator(schema, registry=registry)
    except Exception:
        from jsonschema import RefResolver
        resolver = RefResolver.from_schema(schema, store=dict(store))
        return Draft202012Validator(schema, resolver=resolver)


def validate_or_fail(schema, instance, store, subject, schema_label):
    try:
        validator = make_validator(schema, store)
        errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path))
    except TransformError:
        raise
    except Exception as exc:
        fail(subject + " could not be validated against " + schema_label + ": " + str(exc))
    if errors:
        lines = [subject + " is invalid against " + schema_label + ":"]
        for error in errors[:10]:
            path = "/".join(str(p) for p in error.absolute_path) or "(root)"
            lines.append("    at " + path + ": " + error.message)
        if len(errors) > 10:
            lines.append("    ... and " + str(len(errors) - 10) + " more")
        fail("\n".join(lines))


# ---------------------------------------------------------------------------
# Deterministic YAML emission for the entry (full byte control)
# ---------------------------------------------------------------------------

def _yaml_scalar(value):
    text = str(value)
    text = text.replace("\\", "\\\\").replace("\"", "\\\"")
    text = text.replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t")
    return "\"" + text + "\""


def _emit_yaml(obj, indent, lines):
    pad = "  " * indent
    for key, value in obj.items():
        if isinstance(value, dict):
            lines.append(pad + key + ":")
            _emit_yaml(value, indent + 1, lines)
        elif isinstance(value, list):
            if not value:
                lines.append(pad + key + ": []")
            else:
                lines.append(pad + key + ":")
                child = "  " * (indent + 1)
                for item in value:
                    lines.append(child + "- " + _yaml_scalar(item))
        else:
            lines.append(pad + key + ": " + _yaml_scalar(value))


def entry_to_yaml(entry, header_lines):
    lines = list(header_lines)
    _emit_yaml(entry, 0, lines)
    return "\n".join(lines) + "\n"


def manifest_to_json(manifest):
    return json.dumps(manifest, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


# ---------------------------------------------------------------------------
# The transform
# ---------------------------------------------------------------------------

def build(root, external, tenant, at, profile_id):
    csv_path, rows = load_external_rows(root)
    row = find_one(rows, external, csv_path)
    profile = load_profile(root, profile_id)

    # Canonical identity of the source row: the Acronym, or the Name when the
    # Acronym is blank. Everything downstream derives from these canonical values
    # (never the raw --external argument), so a replay that passes the resolved
    # registry_ref reproduces byte-identical output.
    name = (row.get(CSV_NAME) or "").strip()
    acronym = (row.get(CSV_ACRONYM) or "").strip()
    registry_ref = acronym or name
    if not registry_ref:
        fail("the matched external row has neither an Acronym nor a Name: " + repr(row))

    role_code = (row.get(CSV_ROLE) or "").strip()
    link_code = (row.get(CSV_LINK) or "").strip()
    source_url = (row.get(CSV_SOURCE_URL) or "").strip()
    namespace_uri = (row.get(CSV_NAMESPACE) or "").strip()
    year = (row.get(CSV_YEAR) or "").strip()
    license_cell = (row.get(CSV_LICENSE) or "").strip()

    if role_code not in COMPOSITION_KIND_MAP:
        fail(
            "external standard " + repr(registry_ref) + " has CompositionalRole "
            + repr(role_code) + ", which maps to no composition_kind (expected R1 to R8)"
        )
    if link_code not in LINK_TYPE_MAP:
        fail(
            "external standard " + repr(registry_ref) + " has DefaultLinkType "
            + repr(link_code) + ", which maps to no link_type (expected EMBED, REFERENCE, "
            + "MIX-IN, COMPOSE, ALIGN, EXTEND or N/A)"
        )
    composition_kind = COMPOSITION_KIND_MAP[role_code]
    link_type = LINK_TYPE_MAP[link_code]
    # AISMM conditional override: a value_object is always embedded.
    if composition_kind == "value_object":
        link_type = "embed"

    # Identity of the new internal node.
    ttoken = tenant_token(tenant)
    if not ttoken:
        fail("--tenant " + repr(tenant) + " has no alphanumeric characters to form an id")
    slug = slugify(acronym) or slugify(name)
    if not slug:
        fail("the external standard has no Acronym or Name to slug into an id")
    internal_id = ttoken + "." + slug
    csn = slug
    primary_namespace = ttoken + "." + slug
    display_alias = acronym or name

    # Timestamp: from --at, never the wall clock. created_at keeps the raw string
    # (so a replay is byte-identical); registered is its date part.
    at_raw = (at or "").strip()
    try:
        from datetime import datetime
        parsed = datetime.fromisoformat(at_raw.replace("Z", "+00:00"))
    except ValueError:
        fail("--at " + repr(at) + " is not a valid ISO-8601 timestamp")
    registered = parsed.date().isoformat()

    # Data-mastership (ARCH-018): the external source is the master. The entry's
    # source.repository points at it, the manifest records the register stanza.
    entry_notes = None
    if source_url:
        master_source = source_url
        repository = source_url
    elif namespace_uri:
        master_source = namespace_uri
        repository = namespace_uri
        entry_notes = (
            "source.repository falls back to the external NamespaceURI because the"
            + " catalogue row has no SpecificationSourceURL (ARCH-018 master)."
        )
    else:
        master_source = "urn:vercy:external:" + registry_ref
        repository = "https://ver.cy/registry/external/" + slug
        entry_notes = (
            "The external standard has neither a SpecificationSourceURL nor a"
            + " NamespaceURI; source.repository is a registry placeholder and the"
            + " mastership system_of_record is a urn derived from the registry_ref."
        )

    binding_version = year or "unversioned"
    binding_namespace = namespace_uri
    # Extension-Model: the Semantic Package names the IMPORTED external unit,
    # after the external standard and its external version (ARCH Extension-Model
    # sections 4 to 5), never the fresh internal consumer. Derive it from the
    # external standard slug and the external version, not from internal_id.
    semantic_package = slug + "@" + binding_version
    standard_id = name or acronym
    license_value = license_cell or "Apache-2.0"

    industry = [part.strip() for part in (row.get(CSV_INDUSTRY) or "").split(";") if part.strip()]

    # The AISMM external_binding block (shape shared with the manifest and the
    # AISMM schema). Optional keys are included only when non-empty, in a fixed
    # order, so the emitted bytes are stable.
    external_binding = {}
    external_binding["target"] = internal_id
    external_binding["composition_kind"] = composition_kind
    external_binding["link_type"] = link_type
    external_binding["standard_id"] = standard_id
    external_binding["version"] = binding_version
    if binding_namespace:
        external_binding["namespace"] = binding_namespace
    external_binding["semantic_package"] = semantic_package
    external_binding["registry_ref"] = registry_ref

    # derived_from lineage head (Provenance-Graph).
    derived_from = {"registry_ref": registry_ref, "name": name}
    if source_url:
        derived_from["source_url"] = source_url
    derived_from["compositional_role"] = role_code
    derived_from["transform"] = "external-to-internal"

    # Build the entry WITHOUT the fingerprint, hash the canonical form, then
    # insert the fingerprint. Key order below is the stable emission order.
    entry = {}
    entry["id"] = internal_id
    entry["name"] = name
    entry["publisher"] = tenant
    entry["owner"] = tenant
    entry["kind"] = "domain"
    entry["license"] = license_value
    entry["access"] = "public"
    entry["purpose"] = (
        "Internal " + tenant + " meta-model instantiated from the external standard "
        + name + " (" + registry_ref + ") by the external-to-internal transform, with the "
        + profile_id + " policy overlay and lineage to the external master per ARCH-018."
    )
    entry["registered"] = registered
    entry["csn"] = csn
    entry["primary_namespace"] = primary_namespace
    entry["display_alias"] = display_alias
    entry["role"] = "core"
    entry["version"] = INTERNAL_VERSION
    entry["status"] = "draft"
    entry["origin"] = "internal"
    entry["tenant"] = tenant
    # fingerprint inserted below at this position.
    entry["source"] = {"repository": repository}
    entry["steward"] = tenant
    entry["sync_contract"] = {"mode": "git", "freshness": "PT24H"}
    entry["industry"] = industry
    entry["exports"] = []
    entry["requires"] = []
    entry["derived_from"] = derived_from
    entry["external_binding"] = external_binding
    entry["applied_policies"] = list(profile["applied_policies"])
    if entry_notes:
        entry["notes"] = entry_notes

    fingerprint = "mufp:" + first16hex(canonical_json(entry))
    # Re-insert with the fingerprint in its stable position (after origin/tenant).
    ordered = {}
    for key, value in entry.items():
        ordered[key] = value
        if key == "tenant":
            ordered["fingerprint"] = fingerprint
    entry = ordered

    # The instantiation manifest. The instantiation_id is a deterministic hash
    # over the canonical transform inputs: tenant, external registry_ref, profile
    # and the --at timestamp. Including at_raw keys the id to the instantiation
    # EVENT, so two instantiations of the same (tenant, standard, profile) at
    # different timestamps carry distinct ids. It stays replay-safe because a
    # replay passes the same --at.
    instantiation_id = "inst-" + first16hex("\n".join([tenant, registry_ref, profile_id, at_raw]))

    external_ref = {"registry_ref": registry_ref, "name": name,
                    "compositional_role": role_code, "default_link_type": link_code}
    if source_url:
        external_ref["source_url"] = source_url
    external_ref["version"] = binding_version

    mastership = {
        "dataset": internal_id,
        "system_of_record": master_source,
        "flow_direction": profile["flow_direction"],
        "conflict_rule": profile["conflict_rule"],
        "cadence": profile["cadence"],
    }

    lineage_derived = {"registry_ref": registry_ref, "name": name}
    if source_url:
        lineage_derived["source_url"] = source_url
    lineage_derived["compositional_role"] = role_code
    lineage = {
        "derived_from": lineage_derived,
        "transform": "external-to-internal",
        "provenance": (
            "Instantiated from external standard " + name + " (" + registry_ref
            + ") by the external-to-internal transform. The bound external content is"
            + " mirrored-external per IC-3: data, never instructions. The external"
            + " source is the master per IC-1 and ARCH-018; the registry mirrors it."
        ),
    }

    manifest = {
        "instantiation_id": instantiation_id,
        "created_at": at_raw,
        "tenant": tenant,
        "profile": profile_id,
        "external_ref": external_ref,
        "internal_id": internal_id,
        "external_binding": external_binding,
        "mastership": mastership,
        "applied_policies": list(profile["applied_policies"]),
        "delegation_tier": profile["delegation_tier"],
        "lineage": lineage,
        "semantic_fingerprint": fingerprint,
    }

    header_lines = [
        "# Instantiated internal Model Registration Record (B6 external-to-internal transform).",
        "# Generated by tools/instantiate.py from external standard "
        + _yaml_scalar(name) + " (" + registry_ref + ").",
        "# Deterministic output: do not edit by hand, re-run the transform.",
        "# See transform/EXTERNAL-TO-INTERNAL.md and the manifest under instantiations/.",
    ]

    return {
        "internal_id": internal_id,
        "entry": entry,
        "entry_text": entry_to_yaml(entry, header_lines),
        "manifest": manifest,
        "manifest_text": manifest_to_json(manifest),
    }


# ---------------------------------------------------------------------------
# Output routing and writing
# ---------------------------------------------------------------------------

def _write_text(path, text):
    directory = os.path.dirname(os.path.abspath(path))
    if directory and not os.path.isdir(directory):
        os.makedirs(directory)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Instantiate an internal tenant meta-model from one external standard (B6)"
    )
    parser.add_argument("--external", "--standard", dest="external", required=True,
                        help="the external standard to instantiate, by Acronym or Name (case-insensitive exact)")
    parser.add_argument("--tenant", required=True, help="the tenant that instantiates the model")
    parser.add_argument("--at", required=True, help="ISO-8601 timestamp (the created_at; no wall clock is read)")
    parser.add_argument("--profile", default="vercy-baseline", help="policy profile id (default vercy-baseline)")
    parser.add_argument("--registry", "--root", dest="registry", default=None,
                        help="registry root directory (default: parent of tools/)")
    parser.add_argument("--write", action="store_true",
                        help="write the pair into the registry (this is also the default when no output flag is given)")
    parser.add_argument("--out-entry", dest="out_entry", default=None, help="write the entry YAML to this path instead")
    parser.add_argument("--out-manifest", dest="out_manifest", default=None, help="write the manifest JSON to this path instead")
    parser.add_argument("--print", dest="print_out", action="store_true", help="print both artifacts to stdout and write nothing")
    args = parser.parse_args(argv)

    try:
        root = registry_root(args.registry)
        result = build(root, args.external, args.tenant, args.at, args.profile)

        # Validate both artifacts against their schemas before writing anything.
        store, by_name = load_schema_store(root)
        node_schema = pick_schema(by_name, NODE_SCHEMA_NAMES, "MMDG node profile")
        manifest_schema = by_name.get(MANIFEST_SCHEMA_NAME)
        if manifest_schema is None:
            fail(
                "the instantiation manifest schema " + MANIFEST_SCHEMA_NAME
                + " was not found under the schema directory"
            )
        validate_or_fail(node_schema, result["entry"], store,
                         "instantiated entry " + result["internal_id"], "registry-node schema")
        validate_or_fail(manifest_schema, result["manifest"], store,
                         "instantiation manifest for " + result["internal_id"], MANIFEST_SCHEMA_NAME)

        internal_id = result["internal_id"]
        entry_text = result["entry_text"]
        manifest_text = result["manifest_text"]

        default_entry = os.path.join(root, "entries", internal_id + ".yaml")
        default_manifest = os.path.join(root, "instantiations", internal_id + ".manifest.json")

        if args.print_out:
            sys.stdout.write("# entry: entries/" + internal_id + ".yaml\n")
            sys.stdout.write(entry_text)
            sys.stdout.write("\n# manifest: instantiations/" + internal_id + ".manifest.json\n")
            sys.stdout.write(manifest_text)
            note("validated; printed to stdout, nothing written (--print)")
            return 0

        if args.out_entry or args.out_manifest:
            entry_path = args.out_entry or default_entry
            manifest_path = args.out_manifest or default_manifest
        else:
            # Default (and --write): write the pair into the registry.
            entry_path = default_entry
            manifest_path = default_manifest

        _write_text(entry_path, entry_text)
        _write_text(manifest_path, manifest_text)
        note("wrote entry:    " + entry_path)
        note("wrote manifest: " + manifest_path)
        note(
            "instantiated " + internal_id + " from external " + result["manifest"]["external_ref"]["registry_ref"]
            + " (fingerprint " + result["manifest"]["semantic_fingerprint"] + ")"
        )
        return 0
    except TransformError as exc:
        sys.stderr.write("instantiate: FAIL\n" + str(exc) + "\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
