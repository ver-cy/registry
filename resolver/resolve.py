#!/usr/bin/env python3
# ELMM v0.1 resolver: turns a task descriptor into a context pack and a
# Twin Composition Snapshot, implementing the resolution algorithm of
# ELMM v0.1 sections 7 and 8 (bind-by-reference: ARCH-002 versioning,
# ARCH-003 identity, ARCH-009 Semantic Fingerprint, ARCH-016 composition
# roles, ARCH-017 traversal, ARCH-018 mastership, CORE-009/CORE-012
# projections, OBJ-R29 single anchor, V0-V5 validation, FED-013 discovery).
#
# The single economic parameter is max_tokens (ELMM-I30, ELMM-I38 budget
# row). Resolution is Minimal Version Selection (ELMM-I23, R1): declared_min
# is the sole resolver input; version_range and other publish-time
# predicates are V-gate concerns and never resolver inputs.
#
# DETERMINISM (ELMM-I23): no wall-clock time, no randomness. Every timestamp
# comes from the --observed-at argument or the task descriptor; snapshot ids
# and hashes are content-derived. The same registry state plus the same task
# descriptor plus the same --observed-at always produce byte-identical output.
#
# v0.1 limits: no content fetch (members are summaries under the just-in-time
# dereference rule, ELMM-I37); synchronization is git pull (ELMM-I45); the
# only economic parameter is max_tokens.
#
# Runtime: Python 3, standard library plus PyYAML and jsonschema only.

import argparse
import hashlib
import json
import os
import sys

import yaml

RESOLVER_ID = "elmm-resolver 0.1.0"

# The upstream Meta-Universe registry-entry schema is referenced by the pack
# and snapshot schemas only through #/properties/id. We register a minimal
# stub under its canonical $id so validation resolves offline, deterministically
# and without a private path. This is a transport concern, not a semantic one.
UPSTREAM_ENTRY_ID = "https://meta-universe.org/schemas/2.0/registry-entry.schema.json"
UPSTREAM_ENTRY_STUB = {
    "$id": UPSTREAM_ENTRY_ID,
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {
        "id": {
            "type": "string",
            "pattern": "^[a-z0-9]+(\\.[a-z0-9-]+)+$",
        }
    },
}

WALKABLE_EDGE_TYPES = ("composes", "references")


class ResolveError(Exception):
    """A hard-fail resolution condition (ELMM-I38). Carries a diagnostic."""


# --------------------------------------------------------------------------
# Semantic version comparison (ARCH-002). Minimum-only; MVS never needs more.
# --------------------------------------------------------------------------

def _semver_key(version):
    """Sortable key for a semver string. A release ranks above any prerelease
    of the same core (1.0.0 > 1.0.0-rc.1). Build metadata is ignored."""
    core = version.split("+", 1)[0]
    core, _, pre = core.partition("-")
    parts = core.split(".")
    try:
        nums = tuple(int(p) for p in parts[:3])
    except ValueError:
        raise ResolveError("malformed version string: " + repr(version))
    nums = nums + (0,) * (3 - len(nums))
    # release (no prerelease) sorts after any prerelease of the same core
    pre_key = (1,) if pre == "" else (0, pre)
    return (nums, pre_key)


def _version_lt(a, b):
    return _semver_key(a) < _semver_key(b)


def _max_version(versions):
    best = versions[0]
    for v in versions[1:]:
        if _version_lt(best, v):
            best = v
    return best


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------

def load_registry(root):
    """Load every entries/*.yaml record and mmdg/edges.json from the registry
    root. Returns (models_by_id, edges_list)."""
    entries_dir = os.path.join(root, "entries")
    edges_path = os.path.join(root, "mmdg", "edges.json")
    if not os.path.isdir(entries_dir):
        raise ResolveError("registry has no entries/ directory: " + entries_dir)
    if not os.path.isfile(edges_path):
        raise ResolveError("registry has no mmdg/edges.json: " + edges_path)

    models = {}
    for name in sorted(os.listdir(entries_dir)):
        if not (name.endswith(".yaml") or name.endswith(".yml")):
            continue
        path = os.path.join(entries_dir, name)
        with open(path, "r", encoding="utf-8") as fh:
            record = yaml.safe_load(fh)
        if not isinstance(record, dict) or "id" not in record:
            raise ResolveError("entry file is not a record with an id: " + path)
        mid = record["id"]
        # Highlander at load: at most one record per id (ELMM-I17).
        if mid in models:
            raise ResolveError(
                "two registry records share id " + repr(mid)
                + " (single node per major identity, ELMM-I17): "
                + models[mid]["_source_file"] + " and " + path
            )
        record["_source_file"] = path
        models[mid] = record

    with open(edges_path, "r", encoding="utf-8") as fh:
        edges = json.load(fh)
    if not isinstance(edges, list):
        raise ResolveError("mmdg/edges.json must be a JSON array")

    return models, edges


def _norm_endpoint(ref):
    """An edge endpoint may be version-qualified (id@major, section 6.2);
    the node key is the id without the @major suffix."""
    return ref.split("@", 1)[0]


# --------------------------------------------------------------------------
# Step 1: routing. Namespace-qualified referenced_entities select seed models.
# --------------------------------------------------------------------------

def route_seeds(referenced_entities, models, log):
    """For each referenced_entity 'namespace.kind', find the model whose
    primary_namespace is the namespace prefix and whose exports contain the
    kind. Error clearly on no match (ELMM-I38 unresolvable-hint row)."""
    by_ns = {}
    for mid, rec in models.items():
        ns = rec.get("primary_namespace")
        if ns is not None:
            by_ns.setdefault(ns, []).append(mid)

    seeds = []              # discovery order of seed model ids
    seed_anchor_kind = {}   # model id -> primary referenced kind (anchor)
    for ent in referenced_entities:
        if "." not in ent:
            raise ResolveError(
                "referenced entity is not namespace-qualified: " + repr(ent)
            )
        ns, _, kind = ent.rpartition(".")
        candidates = by_ns.get(ns, [])
        matched = None
        for mid in candidates:
            if kind in (models[mid].get("exports") or []):
                matched = mid
                break
        if matched is None:
            raise ResolveError(
                "no registered model claims referenced entity " + repr(ent)
                + ": no model has primary_namespace " + repr(ns)
                + " exporting kind " + repr(kind)
                + ". Registered namespaces: "
                + ", ".join(sorted(by_ns.keys()))
            )
        if matched not in seed_anchor_kind:
            seed_anchor_kind[matched] = kind
            seeds.append(matched)
        log.append(
            "route: " + ent + " -> " + matched
            + " (primary_namespace " + ns + ", exports " + kind + ")"
        )

    if not seeds:
        raise ResolveError(
            "task descriptor referenced_entities is empty: nothing to resolve"
        )
    return seeds, seed_anchor_kind


# --------------------------------------------------------------------------
# Deprecation redirect (deprecated-in-favor-of), applied to seeds only.
# --------------------------------------------------------------------------

def redirect_deprecated_seeds(seeds, seed_anchor_kind, models, edges, log):
    """A deprecated seed is redirected to its successor along the
    deprecated-in-favor-of edge (ARCH-002, ELMM-I42). This edge is never
    walked as a dependency; it only redirects a deprecated seed."""
    succ = {}
    for e in edges:
        if e.get("edge_type") == "deprecated-in-favor-of":
            succ[_norm_endpoint(e["from"])] = _norm_endpoint(e["to"])

    new_seeds = []
    redirected = {}   # deprecated id -> successor id
    for mid in seeds:
        seen = set()
        cur = mid
        while models.get(cur, {}).get("status") == "deprecated" and cur in succ:
            nxt = succ[cur]
            if nxt in seen or nxt not in models:
                break
            seen.add(nxt)
            log.append("deprecation-redirect: seed " + cur
                       + " -> successor " + nxt + " (deprecated-in-favor-of)")
            redirected[mid] = nxt
            # carry the anchor kind to the successor if it also exports it
            kind = seed_anchor_kind.get(mid)
            if kind is not None and kind in (models[nxt].get("exports") or []):
                seed_anchor_kind.setdefault(nxt, kind)
            cur = nxt
        if cur not in new_seeds:
            new_seeds.append(cur)
    return new_seeds, redirected


# --------------------------------------------------------------------------
# Step 2: transitive walk over composes and references edges.
# --------------------------------------------------------------------------

def transitive_walk(seeds, models, edges, log):
    """Breadth-first closure from the seed set along composes and references
    edges (ELMM-I29 step 2, honoring ELMM-I19 resolvability). Returns the
    resolution order and, per pulled model, the kinds of the edge that first
    reached it (for anchoring)."""
    outgoing = {}
    for e in edges:
        if e.get("edge_type") in WALKABLE_EDGE_TYPES:
            outgoing.setdefault(_norm_endpoint(e["from"]), []).append(e)

    order = []
    seen = set()
    pull_kinds = {}       # model id -> kinds list from the reaching edge
    queue = list(seeds)
    while queue:
        cur = queue.pop(0)
        if cur in seen:
            continue
        seen.add(cur)
        order.append(cur)
        for e in outgoing.get(cur, []):
            to = _norm_endpoint(e["to"])
            if to not in models:
                # ELMM-I38 missing-model row: hard fail, no partial pack.
                raise ResolveError(
                    "edge endpoint missing from registry: edge "
                    + e["from"] + " --" + e["edge_type"] + "--> " + e["to"]
                    + " names target " + repr(to)
                    + " which is not a registered model"
                )
            if to not in seen and to not in pull_kinds:
                pull_kinds[to] = e.get("kinds") or []
            log.append(
                "walk: " + e["edge_type"] + " " + cur + " -> " + to
                + (" (kinds " + ", ".join(e["kinds"]) + ")"
                   if e.get("kinds") else "")
            )
            if to not in seen:
                queue.append(to)
    return order, pull_kinds


# --------------------------------------------------------------------------
# Step 3: Minimal Version Selection.
# --------------------------------------------------------------------------

def minimal_version_selection(order, models, edges, log):
    """For each resolved model gather every declared_min targeting it, from
    participating edges (whose from is in the resolution) and from the requires
    of resolved from-records, take the max, and pin the model's record version,
    which MUST be >= that max (else hard error, ELMM-I38 incompatible-pins).
    A model reached with no participating minimum pins its registered version
    (section 7.1). MVS runs per major identity; ids are already unique."""
    resolved_set = set(order)
    resolved_version = {}
    for mid in order:
        mins = []
        # declared_min from participating incoming edges
        for e in edges:
            if e.get("edge_type") not in WALKABLE_EDGE_TYPES:
                continue
            if _norm_endpoint(e["to"]) != mid:
                continue
            if _norm_endpoint(e["from"]) not in resolved_set:
                continue
            dm = e.get("declared_min")
            if dm:
                mins.append(dm)
        # declared minimums from resolved from-records' requires
        for other in order:
            for req in (models[other].get("requires") or []):
                if req.get("id") == mid and req.get("min_version"):
                    mins.append(req["min_version"])

        record_version = models[mid].get("version")
        if not record_version:
            raise ResolveError("record " + mid + " declares no version")

        if mins:
            floor = _max_version(mins)
            if _version_lt(record_version, floor):
                raise ResolveError(
                    "incompatible pins for " + mid + ": the maximum declared "
                    "minimum is " + floor + " but the registered record version "
                    "is " + record_version + " (record version must be >= the "
                    "MVS floor, ELMM-I38 incompatible-pins)"
                )
            log.append(
                "mvs: " + mid + " max declared minimum " + floor
                + ", registered " + record_version + " -> " + record_version
            )
        else:
            log.append(
                "mvs: " + mid + " no participating minimum, registered "
                + record_version + " -> " + record_version
            )
        resolved_version[mid] = record_version
    return resolved_version


# --------------------------------------------------------------------------
# Step 5: assembly.
# --------------------------------------------------------------------------

def _estimate_tokens(text):
    """Deterministic length-based token estimate: roughly four characters per
    token, rounded up, minimum one. No tokenizer is loaded; the estimate only
    has to be stable and monotone for the single max_tokens budget rule."""
    n = len(text)
    return max(1, (n + 3) // 4)


def _anchor_kind(mid, models, seed_anchor_kind, pull_kinds):
    if mid in seed_anchor_kind:
        return seed_anchor_kind[mid]
    reach = pull_kinds.get(mid) or []
    if reach:
        return reach[0]
    exports = models[mid].get("exports") or []
    if exports:
        return exports[0]
    return None


def _summary_content(rec, anchor, exports):
    purpose = (rec.get("purpose") or rec.get("name") or rec.get("csn")
               or rec["id"]).strip()
    exp = ", ".join(exports) if exports else "none declared"
    return (
        "Summary projection anchored on " + anchor + ". Purpose: " + purpose
        + " Exported kinds: " + exp + ". Identifiers plus a short summary under "
        "the just-in-time dereference rule; dereference any identifier for the "
        "full projection."
    )


def _terse_content(anchor):
    return (
        "Summary withheld to fit the token budget. Anchor " + anchor
        + " is present as an identifier only; dereference on demand."
    )


def assemble_pack(task_ref, descriptor, order, models, resolved_version,
                  seed_anchor_kind, pull_kinds, seeds, redirected,
                  registry_ref, observed_at, log):
    seed_set = set(seeds)
    max_tokens = descriptor["max_tokens"]

    members = []
    for mid in order:
        rec = models[mid]
        exports = rec.get("exports") or []
        kind = _anchor_kind(mid, models, seed_anchor_kind, pull_kinds)
        if kind is None:
            raise ResolveError(
                "cannot anchor member " + mid + ": no referenced kind, no "
                "reaching-edge kind and no exports to anchor on (OBJ-R29)"
            )
        ns = rec.get("primary_namespace") or mid
        anchor = ns + "." + kind
        version = resolved_version[mid]
        fp = rec.get("fingerprint", "")
        src_ref = (rec.get("source") or {}).get("ref", "")
        content = _summary_content(rec, anchor, exports)
        provenance = (
            "Projected from " + mid + " " + version + " (" + fp
            + "), source ref " + (src_ref or "unspecified")
            + ", registry " + registry_ref + "."
        )
        members.append({
            "model_id": mid,
            "anchor": anchor,
            "form": "summary",
            "content": content,
            "provenance": provenance,
            "tokens": _estimate_tokens(content),
            "_priority": 0 if mid in seed_set else 1,
        })

    # Budget rule (ELMM-I38 budget row): degrade lower-priority members to a
    # terser summary until within max_tokens, recording each degradation.
    degraded = []
    total = sum(m["tokens"] for m in members)
    if total > max_tokens:
        # lowest priority first, then later assembly position first
        candidates = sorted(
            range(len(members)),
            key=lambda i: (members[i]["_priority"], i),
            reverse=True,
        )
        for i in candidates:
            if total <= max_tokens:
                break
            m = members[i]
            terse = _terse_content(m["anchor"])
            new_tokens = _estimate_tokens(terse)
            if new_tokens >= m["tokens"]:
                continue
            total -= (m["tokens"] - new_tokens)
            m["content"] = terse
            m["tokens"] = new_tokens
            degraded.append(m["model_id"])
            log.append("budget: degraded " + m["model_id"]
                       + " to terse summary to fit max_tokens")
    log.append("budget: " + str(total) + " of " + str(max_tokens)
               + " tokens" + (" after degradation" if degraded else ""))

    for m in members:
        del m["_priority"]

    version_pins = [
        {
            "id": mid,
            "version": resolved_version[mid],
            "semantic_fingerprint": models[mid].get("fingerprint", ""),
        }
        for mid in order
    ]

    # Exclusions: registered models deliberately not pulled, with reason,
    # plus deprecated seeds that were redirected (least privilege, ELMM-I35).
    resolved_ids = set(order)
    exclusions = []
    for mid in sorted(models.keys()):
        if mid in resolved_ids or mid in redirected:
            continue
        rec = models[mid]
        role = rec.get("role")
        status = rec.get("status")
        if role == "kernel":
            reason = ("kernel node, not task content; the kernel declares no "
                      "outgoing edges (least privilege)")
        elif status == "deprecated":
            reason = "deprecated and reached by no walkable edge"
        else:
            reason = ("not reachable from the routed seeds along composes or "
                      "references edges (minimal-sufficient)")
        exclusions.append(mid + ": " + reason)
    for dep, succ in redirected.items():
        exclusions.append(
            dep + ": deprecated, redirected to successor " + succ
            + " (deprecated-in-favor-of)"
        )

    covered = ", ".join(m["anchor"] for m in members)
    coverage = (
        "Covers " + covered + " as summary projections under the just-in-time "
        "dereference rule (v0.1 emits no full content: sync is git pull and "
        "members carry identifiers plus short summaries). "
    )
    if degraded:
        coverage += ("Budget degradation: " + ", ".join(sorted(set(degraded)))
                     + " reduced to terse summaries to fit " + str(max_tokens)
                     + " tokens; used " + str(total) + " tokens. ")
    else:
        coverage += ("Budget used " + str(total) + " of " + str(max_tokens)
                     + " tokens; no degradation occurred. ")
    coverage += ("observed_at is the caller-supplied stamp (deterministic, no "
                 "wall clock); no staleness computed against sync_contract "
                 "freshness in v0.1. Nothing else is reachable from the seed "
                 "set along composes or references edges.")

    pack = {
        "task_ref": task_ref,
        "member_projections": members,
        "coverage_statement": coverage,
        "version_pins": version_pins,
        "provenance": {
            "registry_ref": registry_ref,
            "resolver": RESOLVER_ID,
            "routing_log": list(log),
        },
        "observed_at": observed_at,
        "max_tokens": max_tokens,
        "exclusions": exclusions,
        "requester_identity": descriptor["requester_identity"],
        "purpose": descriptor["purpose"],
    }
    return pack


# --------------------------------------------------------------------------
# Step 6: the Twin Composition Snapshot.
# --------------------------------------------------------------------------

def _canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def build_snapshot(task_ref, order, models, resolved_version, edges,
                   observed_at):
    resolved = [
        {
            "id": mid,
            "version": resolved_version[mid],
            "semantic_fingerprint": models[mid].get("fingerprint", ""),
            "source_ref": (models[mid].get("source") or {}).get("ref", ""),
        }
        for mid in order
    ]

    # edges_hash: sha256 over the canonicalized edge file (sort_keys, no
    # insignificant whitespace). Non-semantic transport-integrity field.
    edges_hash = "sha256:" + hashlib.sha256(
        _canonical(edges).encode("utf-8")
    ).hexdigest()

    # snapshot_id: content-derived, never random. Over the canonical resolved
    # set (order-independent) plus the edges hash plus the task ref.
    resolved_sorted = sorted(resolved, key=lambda r: r["id"])
    material = _canonical(resolved_sorted) + edges_hash + task_ref
    snapshot_id = "tcs-" + hashlib.sha256(
        material.encode("utf-8")
    ).hexdigest()[:16]

    snapshot = {
        "snapshot_id": snapshot_id,
        "resolved": resolved,
        "edges_hash": edges_hash,
        "created_at": observed_at,
        "task_ref": task_ref,
    }
    return snapshot


# --------------------------------------------------------------------------
# Validation (V0). Offline, deterministic.
# --------------------------------------------------------------------------

def _find_schema_dir(explicit, script_dir, registry_root):
    candidates = []
    if explicit:
        candidates.append(explicit)
    # The shipped layout keeps the schemas at registry/schema (singular), one
    # level up from resolver/. Probe that first, then legacy plural fallbacks.
    candidates.append(os.path.join(script_dir, "..", "schema"))
    candidates.append(os.path.join(registry_root, "schema"))
    candidates.append(os.path.join(registry_root, "..", "schema"))
    candidates.append(os.path.join(script_dir, "..", "..", "schemas"))
    candidates.append(os.path.join(registry_root, "schemas"))
    candidates.append(os.path.join(registry_root, "..", "schemas"))
    candidates.append(os.path.join(registry_root, "..", "profile", "schemas"))
    for c in candidates:
        c = os.path.normpath(c)
        if os.path.isfile(os.path.join(c, "context-pack.schema.json")):
            return c
    return None


def validate_outputs(pack, snapshot, schema_dir):
    """Validate the pack and snapshot against the published schemas. The
    schemas $ref the upstream registry-entry schema only at #/properties/id;
    a minimal stub is registered under its canonical $id so resolution is
    offline and needs no private path."""
    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource

    def load(name):
        with open(os.path.join(schema_dir, name), "r", encoding="utf-8") as fh:
            return json.load(fh)

    pack_schema = load("context-pack.schema.json")
    snap_schema = load("twin-snapshot.schema.json")

    registry = Registry().with_resources([
        (UPSTREAM_ENTRY_ID, Resource.from_contents(UPSTREAM_ENTRY_STUB)),
        (pack_schema["$id"], Resource.from_contents(pack_schema)),
        (snap_schema["$id"], Resource.from_contents(snap_schema)),
    ])

    for label, schema, instance in (
        ("context pack", pack_schema, pack),
        ("twin snapshot", snap_schema, snapshot),
    ):
        validator = Draft202012Validator(schema, registry=registry)
        errors = sorted(validator.iter_errors(instance), key=lambda e: e.path)
        if errors:
            first = errors[0]
            loc = "/".join(str(p) for p in first.path) or "(root)"
            raise ResolveError(
                "emitted " + label + " failed schema validation at " + loc
                + ": " + first.message
            )


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------

def mint_task_ref(descriptor):
    """Deterministic task ref when the descriptor omits one:
    'task-' + sha1(purpose + requester_identity)[:12]."""
    material = (descriptor.get("purpose", "")
               + descriptor.get("requester_identity", ""))
    return "task-" + hashlib.sha1(material.encode("utf-8")).hexdigest()[:12]


def resolve(descriptor, registry_root, registry_ref, observed_at, schema_dir,
            do_validate):
    for field in ("purpose", "requester_identity", "referenced_entities",
                  "max_tokens"):
        if field not in descriptor:
            raise ResolveError("task descriptor is missing required field: "
                               + field)

    task_ref = descriptor.get("task_ref") or mint_task_ref(descriptor)
    log = []
    log.append("registry_ref: " + registry_ref)
    log.append("observed_at: " + observed_at)
    log.append("task_ref: " + task_ref)

    models, edges = load_registry(registry_root)
    log.append("loaded " + str(len(models)) + " records and "
               + str(len(edges)) + " edges")

    seeds, seed_anchor_kind = route_seeds(
        descriptor["referenced_entities"], models, log)
    seeds, redirected = redirect_deprecated_seeds(
        seeds, seed_anchor_kind, models, edges, log)
    log.append("seed set: " + ", ".join(seeds))

    order, pull_kinds = transitive_walk(seeds, models, edges, log)
    log.append("resolution closure: " + ", ".join(order))

    resolved_version = minimal_version_selection(order, models, edges, log)

    pack = assemble_pack(
        task_ref, descriptor, order, models, resolved_version,
        seed_anchor_kind, pull_kinds, seeds, redirected,
        registry_ref, observed_at, log)

    snapshot = build_snapshot(
        task_ref, order, models, resolved_version, edges, observed_at)

    if do_validate:
        if schema_dir is None:
            sys.stderr.write(
                "warning: schema directory not found; skipping output "
                "validation. Pass --schemas-dir to enable it.\n")
        else:
            validate_outputs(pack, snapshot, schema_dir)

    return pack, snapshot


def _write(path, obj):
    text = json.dumps(obj, indent=2, ensure_ascii=True) + "\n"
    if path is None or path == "-":
        sys.stdout.write(text)
    else:
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="ELMM v0.1 resolver: task descriptor -> context pack + "
                    "Twin Composition Snapshot (deterministic).")
    parser.add_argument("--task", required=True,
                        help="path to the task descriptor JSON")
    parser.add_argument("--registry", "--root", dest="registry", required=True,
                        help="registry root holding entries/ and "
                             "mmdg/edges.json (--root is an accepted alias, "
                             "used by CI)")
    parser.add_argument("--observed-at", required=True,
                        help="ISO 8601 timestamp used for observed_at and "
                             "created_at (no wall clock is ever read)")
    parser.add_argument("--registry-ref", default="uncommitted",
                        help="registry repository state, e.g. a git commit; "
                             "recorded as provenance.registry_ref "
                             "(default: uncommitted)")
    parser.add_argument("--out-pack", default=None,
                        help="output path for the context pack (default: "
                             "combined stdout object)")
    parser.add_argument("--out-snapshot", default=None,
                        help="output path for the snapshot (default: combined "
                             "stdout object)")
    parser.add_argument("--schemas-dir", default=None,
                        help="directory holding the .schema.json files "
                             "(auto-discovered when omitted)")
    parser.add_argument("--no-validate", action="store_true",
                        help="skip validating the emitted pack and snapshot")
    args = parser.parse_args(argv)

    try:
        with open(args.task, "r", encoding="utf-8") as fh:
            descriptor = json.load(fh)
    except (OSError, ValueError) as exc:
        sys.stderr.write("error: cannot read task descriptor "
                         + repr(args.task) + ": " + str(exc) + "\n")
        return 2

    script_dir = os.path.dirname(os.path.abspath(__file__))
    schema_dir = _find_schema_dir(
        args.schemas_dir, script_dir, os.path.abspath(args.registry))

    if args.out_pack and args.out_snapshot and (
            args.out_pack == args.out_snapshot):
        sys.stderr.write("error: --out-pack and --out-snapshot must differ\n")
        return 2

    try:
        pack, snapshot = resolve(
            descriptor, args.registry, args.registry_ref, args.observed_at,
            schema_dir, do_validate=not args.no_validate)
    except ResolveError as exc:
        sys.stderr.write("error: " + str(exc) + "\n")
        return 1
    except Exception as exc:  # unexpected: still fail non-zero with a diagnostic
        sys.stderr.write("error: unexpected failure: " + repr(exc) + "\n")
        return 1

    # When neither output path is given, emit a single combined JSON object so
    # one json.loads recovers both artifacts. This is the CI resolver contract
    # (keys context_pack and twin_snapshot); no stray banner text on stdout.
    if not args.out_pack and not args.out_snapshot:
        combined = {"context_pack": pack, "twin_snapshot": snapshot}
        sys.stdout.write(
            json.dumps(combined, indent=2, ensure_ascii=True) + "\n")
    else:
        _write(args.out_pack, pack)
        _write(args.out_snapshot, snapshot)
    return 0


if __name__ == "__main__":
    sys.exit(main())
