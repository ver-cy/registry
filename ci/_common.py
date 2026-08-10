"""Shared helpers for the ELMM registry CI checks.

The registry repository is the specification, and these helpers are the load
bearing plumbing the four checks share: locating the registry root, loading
the entries, the edge file and the JSON Schemas, building a jsonschema
validator whose cross document $ref targets resolve locally (offline and
deterministic), and invoking the reference runtime under a fixed contract.

Design notes bound to the ELMM v0.1 profile:

  - Identity is registry id plus Canonical Semantic Name plus Namespace
    (ARCH-003), versioned per ARCH-002; the semantic pin is the Semantic
    Fingerprint per ARCH-009, never a byte hash. These helpers never treat a
    byte digest as a semantic pin.
  - The node profile (registry-node.schema.json) is a profile over the upstream
    Meta-Universe registry entry schema (entry.schema.json), not a fifth
    schema: fields shared with the upstream entry keep their upstream names and
    shapes and are bound by reference (id, steward, fingerprint,
    primary_namespace, source), and the profile adds the MMDG node fields (role,
    exports, requires, sync_contract) plus the profile-local fields (csn,
    display_alias, industry, origin, provenance, routing_hints). Because the
    upstream schema is additionalProperties:false and the extension fields are
    pending upstream change requests CR-1 and CR-2, an entry validates in full
    against the node profile and, on its upstream-field projection, against the
    unmodified upstream entry schema. That projection is the convergence proof;
    the full record is never offered to the upstream schema.
  - Determinism is mandatory (ELMM-I23): no wall clock, no random. Any
    timestamp comes from a CLI argument or a fixed constant, never from the
    system clock.

Runtime dependencies: Python 3 standard library, PyYAML, jsonschema. No others.
"""

import glob
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

try:
    import yaml
except ImportError as exc:  # pragma: no cover - environment guard
    sys.stderr.write(
        "FAIL: PyYAML is required (pip install pyyaml): " + str(exc) + "\n"
    )
    raise

# The upstream Meta-Universe registry entry schema, referenced by $id. The node
# profile binds upstream fields by reference through this $id, so the upstream
# schema is vendored under the registry schema directory both to resolve those
# references and to run the projection convergence proof.
UPSTREAM_ENTRY_ID = "https://meta-universe.org/schemas/2.0/registry-entry.schema.json"

# Fixed observation timestamp for the resolver. Determinism (ELMM-I23) forbids a
# wall clock read; the value is a constant, overridable only by an explicit
# environment variable so a caller can pin a different fixed instant.
OBSERVED_AT = os.environ.get("ELMM_OBSERVED_AT", "2026-08-09T10:15:00Z")

# Candidate file names for each schema, in preference order. The task pins the
# node schema name to registry-node.schema.json; the source repository ships it
# as mmdg-node.schema.json, kept here as a fallback so the checks run against
# either layout.
NODE_SCHEMA_NAMES = ("registry-node.schema.json", "mmdg-node.schema.json")
EDGE_SCHEMA_NAMES = ("mmdg-edge.schema.json", "registry-edge.schema.json")
TASK_SCHEMA_NAMES = ("task-descriptor.schema.json",)
PACK_SCHEMA_NAMES = ("context-pack.schema.json",)
SNAPSHOT_SCHEMA_NAMES = ("twin-snapshot.schema.json", "twin-composition-snapshot.schema.json")


class CheckError(Exception):
    """A CI violation with a precise, human readable diagnostic."""


def info(message):
    sys.stdout.write(message + "\n")


def ok(message):
    sys.stdout.write("  ok  " + message + "\n")


# ---------------------------------------------------------------------------
# Root and file location
# ---------------------------------------------------------------------------

def registry_root(explicit=None):
    """Return the registry root directory.

    When explicit is given it is used verbatim. Otherwise the root is the
    parent of the directory holding this module (the checks live in
    <root>/ci/), which makes every check working directory independent and
    reusable on a copied tree.
    """
    if explicit:
        return os.path.abspath(explicit)
    return os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))


def entries_dir(root):
    return os.path.join(root, "entries")


def schema_dir(root):
    return os.path.join(root, "schema")


def edges_path(root):
    return os.path.join(root, "mmdg", "edges.json")


def examples_dir(root):
    return os.path.join(root, "examples")


def resolver_path(root):
    return os.path.join(root, "resolver", "resolve.py")


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_json_file(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        raise CheckError("file not found: " + path)
    except json.JSONDecodeError as exc:
        raise CheckError("invalid JSON in " + path + ": " + str(exc))


def load_yaml_file(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return yaml.safe_load(handle)
    except FileNotFoundError:
        raise CheckError("file not found: " + path)
    except yaml.YAMLError as exc:
        raise CheckError("invalid YAML in " + path + ": " + str(exc))


def load_entries(root):
    """Return a sorted list of (path, record) for every registry entry."""
    directory = entries_dir(root)
    if not os.path.isdir(directory):
        raise CheckError("entries directory not found: " + directory)
    paths = sorted(
        glob.glob(os.path.join(directory, "*.yaml"))
        + glob.glob(os.path.join(directory, "*.yml"))
    )
    if not paths:
        raise CheckError("no entry files found under " + directory)
    records = []
    for path in paths:
        data = load_yaml_file(path)
        if not isinstance(data, dict):
            raise CheckError("entry is not a mapping: " + path)
        records.append((path, data))
    return records


def load_edges(root):
    """Return (path, list of edge records)."""
    path = edges_path(root)
    data = load_json_file(path)
    if not isinstance(data, list):
        raise CheckError("edge file is not a JSON array: " + path)
    return path, data


def load_schema_store(root):
    """Load every JSON Schema reachable from the registry.

    Returns (store, by_name):
      store   maps $id -> schema document, for cross document $ref resolution.
      by_name maps basename -> schema document, for selecting a schema by file.

    Every *.json under the schema directory is loaded. The upstream entry
    schema, if vendored anywhere under the registry root, is picked up by its
    $id in a bounded secondary scan: the node profile binds upstream fields by
    reference through that $id, and the projection convergence proof validates
    against it directly.
    """
    directory = schema_dir(root)
    if not os.path.isdir(directory):
        raise CheckError("schema directory not found: " + directory)

    store = {}
    by_name = {}

    def ingest(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as handle:
                doc = json.load(handle)
        except json.JSONDecodeError as exc:
            raise CheckError("invalid JSON schema " + json_path + ": " + str(exc))
        if isinstance(doc, dict):
            schema_id = doc.get("$id")
            if schema_id:
                store[schema_id] = doc
            by_name.setdefault(os.path.basename(json_path), doc)

    for dirpath, _dirs, files in os.walk(directory):
        for name in sorted(files):
            if name.endswith(".json"):
                ingest(os.path.join(dirpath, name))

    # Secondary scan for an upstream entry schema vendored outside the schema
    # directory. Cheap and bounded: only runs when it is missing.
    if UPSTREAM_ENTRY_ID not in store:
        for dirpath, _dirs, files in os.walk(root):
            if os.path.abspath(dirpath) == os.path.abspath(directory):
                continue
            for name in sorted(files):
                if name.endswith(".json"):
                    candidate = os.path.join(dirpath, name)
                    try:
                        with open(candidate, "r", encoding="utf-8") as handle:
                            doc = json.load(handle)
                    except (json.JSONDecodeError, OSError):
                        continue
                    if isinstance(doc, dict) and doc.get("$id") == UPSTREAM_ENTRY_ID:
                        store[UPSTREAM_ENTRY_ID] = doc
                        by_name.setdefault(os.path.basename(candidate), doc)
                        break
            if UPSTREAM_ENTRY_ID in store:
                break

    return store, by_name


def pick_schema(by_name, names, label):
    for candidate in names:
        if candidate in by_name:
            return by_name[candidate]
    raise CheckError(
        "could not find the " + label + " schema; looked for "
        + ", ".join(names) + " under the registry schema directory"
    )


def project_to_upstream(record, upstream_schema):
    """Project a converged entry onto the upstream entry schema's field set.

    The upstream schema is additionalProperties:false and the profile extension
    fields (role, exports, requires, sync_contract) and the profile-local
    fields (csn, display_alias, industry, origin, provenance, routing_hints)
    are pending upstream change requests CR-1 and CR-2, so the full record is
    never offered to the upstream schema. The projection keeps only the keys
    the upstream schema declares as properties, which is exactly the set the
    convergence proof asserts the entry satisfies.
    """
    props = upstream_schema.get("properties", {}) if isinstance(upstream_schema, dict) else {}
    allowed = set(props.keys())
    return {key: value for key, value in record.items() if key in allowed}


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def make_validator(schema, store):
    """Build a Draft 2020-12 validator whose $ref targets resolve from store.

    Prefers the modern referencing based API (jsonschema >= 4.18); falls back
    to the legacy RefResolver so the checks run on older jsonschema too.
    """
    from jsonschema import Draft202012Validator

    try:
        from referencing import Registry, Resource

        resources = []
        for schema_id, doc in store.items():
            resources.append((schema_id, Resource.from_contents(doc)))
        registry = Registry().with_resources(resources)
        return Draft202012Validator(schema, registry=registry)
    except Exception:
        from jsonschema import RefResolver

        resolver = RefResolver.from_schema(schema, store=dict(store))
        return Draft202012Validator(schema, resolver=resolver)


def _format_path(error):
    parts = [str(p) for p in error.absolute_path]
    return "/".join(parts) if parts else "(root)"


def validate_or_raise(schema, instance, store, subject, schema_label, max_errors=10):
    """Validate instance against schema; raise CheckError listing violations."""
    try:
        validator = make_validator(schema, store)
        errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path))
    except CheckError:
        raise
    except Exception as exc:
        raise CheckError(
            subject + " could not be validated against " + schema_label
            + " (schema resolution failed, is any referenced upstream schema"
            + " vendored under the registry schema directory?): " + str(exc)
        )
    if errors:
        lines = [subject + " is invalid against " + schema_label + ":"]
        for error in errors[:max_errors]:
            lines.append("    at " + _format_path(error) + ": " + error.message)
        if len(errors) > max_errors:
            lines.append("    ... and " + str(len(errors) - max_errors) + " more")
        raise CheckError("\n".join(lines))


# ---------------------------------------------------------------------------
# Resolver contract
# ---------------------------------------------------------------------------
#
# The reference runtime at <root>/resolver/resolve.py is invoked as:
#
#     python resolve.py --task <task.json> --registry <root> \
#         --observed-at <iso8601> --out-pack <pack.json> --out-snapshot <snap.json>
#
# The resolver writes the context pack and the Twin Composition Snapshot to the
# two output files (its file output mode). CI reads them back and presents them
# to the rest of the checks as one canonical JSON object:
#
#     {"context_pack": { ... }, "twin_snapshot": { ... }}
#
# The fixed --observed-at makes the run bit reproducible (ELMM-I23): the pack
# observed_at, the snapshot created_at and the deterministically derived
# snapshot_id are all functions of the input and this argument, never of the
# wall clock. On any resolver failure it exits non-zero with a diagnostic on
# stderr and writes no partial pack.

def run_resolver(root, task_path, observed_at, resolver=None):
    """Run the resolver once under the CI contract.

    Invokes the reference runtime with --registry and file outputs, reads the
    two output files back, and returns them as one canonical JSON object so the
    determinism and validity checks see a single
    {"context_pack": ..., "twin_snapshot": ...} document. Determinism holds
    because canonicalization sorts keys and drops insignificant whitespace, so
    identical resolver output yields identical returned bytes.

    Return (returncode, combined_stdout_bytes, stderr_text). On a non-zero exit
    the combined bytes are empty and the caller surfaces stderr.
    """
    script = resolver or resolver_path(root)
    if not os.path.isfile(script):
        raise CheckError("resolver script not found: " + script)
    out_dir = tempfile.mkdtemp(prefix="elmm-resolve-")
    pack_out = os.path.join(out_dir, "pack.json")
    snapshot_out = os.path.join(out_dir, "snapshot.json")
    command = [
        sys.executable,
        script,
        "--task", task_path,
        "--registry", root,
        "--observed-at", observed_at,
        "--out-pack", pack_out,
        "--out-snapshot", snapshot_out,
    ]
    try:
        proc = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stderr_text = proc.stderr.decode("utf-8", "replace")
        if proc.returncode != 0:
            return proc.returncode, b"", stderr_text
        if not (os.path.isfile(pack_out) and os.path.isfile(snapshot_out)):
            raise CheckError(
                "the resolver exited 0 but did not write both output files"
                + " (expected --out-pack and --out-snapshot): " + pack_out
                + " and " + snapshot_out
            )
        pack = load_json_file(pack_out)
        snapshot = load_json_file(snapshot_out)
        combined = canonical_json({"context_pack": pack, "twin_snapshot": snapshot})
        return proc.returncode, combined.encode("utf-8"), stderr_text
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


def extract_pack_and_snapshot(stdout_bytes, subject):
    """Parse the resolver output into (context_pack, twin_snapshot)."""
    try:
        doc = json.loads(stdout_bytes.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise CheckError(subject + ": resolver output is not valid JSON: " + str(exc))
    if not isinstance(doc, dict):
        raise CheckError(subject + ": resolver output is not a JSON object")
    pack = doc.get("context_pack", doc.get("pack"))
    snapshot = doc.get("twin_snapshot", doc.get("snapshot", doc.get("twin_composition_snapshot")))
    if pack is None:
        raise CheckError(subject + ": resolver output has no context_pack")
    if snapshot is None:
        raise CheckError(subject + ": resolver output has no twin_snapshot")
    return pack, snapshot


# ---------------------------------------------------------------------------
# Hashing (transport integrity, never a semantic pin)
# ---------------------------------------------------------------------------

def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hash_tree(directory):
    """Map relative path -> sha256 for every file under directory.

    Used to prove that registering a new domain leaves the kernel (schema and
    resolver) byte for byte unchanged. This is a transport integrity digest,
    clearly not a semantic pin.
    """
    result = {}
    if not os.path.isdir(directory):
        return result
    for dirpath, _dirs, files in os.walk(directory):
        for name in sorted(files):
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, directory).replace(os.sep, "/")
            result[rel] = sha256_file(full)
    return result


def canonical_json(obj):
    """Stable canonical serialization for byte comparison of JSON values."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
