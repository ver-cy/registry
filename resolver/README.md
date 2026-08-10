# ELMM v0.1 resolver

One Python script that turns a task descriptor into a context pack and a Twin
Composition Snapshot, implementing the ELMM v0.1 resolution algorithm
(profile sections 7 and 8). It is the whole runtime of the walking skeleton:
no service, no daemon, one script invoked per task.

## Run it

```
python resolve.py --task <task.json> --registry <registry-root> \
                  --observed-at <ISO8601> [--registry-ref <ref>] \
                  [--out-pack <path>] [--out-snapshot <path>] \
                  [--schemas-dir <dir>] [--no-validate]
```

- `--task` : a task descriptor JSON validating against
  `task-descriptor.schema.json` (`purpose`, `requester_identity`,
  `referenced_entities`, `max_tokens`, optional `task_ref` and
  `freshness_requirement`).
- `--registry` : the registry root holding `entries/*.yaml` (Model
  Registration Records) and `mmdg/edges.json` (the edge file). `--root` is an
  accepted alias for the same option; the CI harness invokes the resolver with
  `--root`.
- `--observed-at` : the ISO 8601 timestamp written into the pack's
  `observed_at` and the snapshot's `created_at`. Supplied by the caller so the
  run reads no wall clock.
- `--registry-ref` : the registry repository state, for example a git commit,
  recorded as `provenance.registry_ref`. Defaults to `uncommitted`.
- `--out-pack` / `--out-snapshot` : output paths. When both are omitted, the
  pack and the snapshot are printed to stdout as one combined JSON object with
  keys `context_pack` and `twin_snapshot`, so a single `json.loads` recovers
  both (the shape the CI harness consumes); when set, each artifact is written
  to its own file.
- `--schemas-dir` : where the `.schema.json` files live. Auto-discovered when
  omitted (it looks one directory up from the script at `registry/schema`,
  then under the registry root, before falling back to legacy `schemas`
  locations). Discovery lets the resolver validate its own output.
- `--no-validate` : skip validating the emitted pack and snapshot.

Exit code is `0` on success and non-zero with a one-line diagnostic on stderr
for any failure.

Example, resolving one real task over the worked-example registry:

```
python resolve.py --task task.json --registry ../ \
                  --observed-at 2026-08-09T10:15:00Z --registry-ref git:2f6d0b1 \
                  --out-pack pack.json --out-snapshot snapshot.json
```

Runtime dependencies: Python 3, the standard library, PyYAML and jsonschema.
No other packages.

## The algorithm in brief

The resolver executes the five ordered steps of ELMM-I29.

1. **Route.** For each namespace-qualified `referenced_entity` (`namespace.kind`,
   for example `plmm.product`) it finds the seed model whose
   `primary_namespace` is the namespace and whose `exports` contain the kind.
   A referenced entity that matches no model is a hard fail (ELMM-I38
   unresolvable-hint row): the diagnostic reproduces the entity and lists the
   registered namespaces. A deprecated seed carrying a
   `deprecated-in-favor-of` edge is redirected to its successor; that edge is
   only ever a redirect, never a walked dependency. (Records may also declare
   `routing_hints`; in v0.1 those are declared-but-unused forward-compatibility
   metadata, not a resolver input.)
2. **Walk.** From the seed set it follows outgoing `composes` and `references`
   edges to a fixpoint, pulling in the transitive closure of required models.
   An edge whose endpoint is absent from the registry is a hard fail (missing
   model), naming the edge and the missing endpoint.
3. **Minimal Version Selection.** For each pulled model it gathers every
   `declared_min` targeting the model (from participating edges and from the
   `requires` of resolved records), takes the maximum, and pins the model's
   registered record version, which must be at least that maximum. A record
   version below the maximum declared minimum is a hard fail (incompatible
   pins). Exactly one node exists per major identity (the highlander rule); two
   records sharing an `id` is a hard fail. `version_range` and any other
   publish-time predicate are never read here (R1, ELMM-I24).
4. **Assemble.** It builds one member projection per resolved model, each
   anchored on the namespace-qualified name of the model's primary referenced
   kind (exactly one anchor per member, OBJ-R29). Members default to `summary`
   form: a short summary drawn from the record's purpose and exports under the
   just-in-time dereference rule. Each member carries provenance (resolved
   version, Semantic Fingerprint, source ref, registry ref). The pack carries
   `version_pins` (the MVS result), pack-level provenance with the full
   routing log, `observed_at`, `max_tokens`, and `exclusions` (registered
   models deliberately not pulled, each with a reason). If the summed member
   token estimate exceeds `max_tokens`, lower-priority members are degraded to
   a terser summary until the pack fits, and every degradation is recorded in
   the coverage statement. Token cost is a length-based estimate, roughly four
   characters per token, rounded up; no tokenizer is loaded.
5. **Snapshot.** It emits the Twin Composition Snapshot: `resolved[]` (id,
   version, semantic_fingerprint, source_ref), `edges_hash` (`sha256:` over the
   canonicalized edge file), `created_at` from `--observed-at`, and a
   content-derived `snapshot_id`.

By default the emitted pack is validated against `context-pack.schema.json`
and the snapshot against `twin-snapshot.schema.json` before either is written.

## Determinism guarantee

The resolver is bit-reproducible. The same registry state, the same task
descriptor and the same `--observed-at` produce byte-identical output on every
run and every machine (ELMM-I23). There is no wall-clock read and no
randomness anywhere:

- every timestamp comes from `--observed-at` (or a field in the input);
- `edges_hash` is `sha256:` plus the SHA-256 of the edge file canonicalized
  with `json.dumps(..., sort_keys=True, separators=(",", ":"))`;
- `snapshot_id` is `tcs-` plus the first 16 hex characters of a SHA-256 over
  the canonical resolved set, the edges hash and the task ref;
- a `task_ref` absent from the descriptor is minted as `task-` plus
  `sha1(purpose + requester_identity)[:12]`, not from a clock or a counter;
- Minimal Version Selection uses no solver, no backtracking and no upper
  bounds, so it always returns the same version set.

`edges_hash`, `snapshot_id` and `source_ref` are byte-level
transport-integrity fields and are labelled as such; the semantic pin is
always the ARCH-009 Semantic Fingerprint, never a byte hash.

## v0.1 limits

- **No content fetch.** Members are projections, not model dumps, and in v0.1
  they are summaries: identifiers plus short summaries under the just-in-time
  dereference rule. The resolver does not open the source repositories; it
  reads the registration records and pins them.
- **Sync is git pull.** The registry repository is the only durable component.
  There is no reconciliation loop and no long-running process. Freshness is a
  declared `sync_contract` on each record; `observed_at` is the caller-supplied
  stamp and travels into the pack.
- **One economic parameter.** `max_tokens` is the whole budget mechanism.
  Overflow degrades members to terser summaries and records it in the coverage
  statement. There is no retrieval-strategy taxonomy, no precomputed rollups
  and no multi-rung degradation ladder.
- **Interim authorization.** The pack carries `requester_identity` and
  `purpose`; the projection builder is the named enforcement point, deny by
  default when a declared entitlement mapping cannot be evaluated. v0.1 runs in
  a single owner-controlled trust domain and onboards no multi-tenant consumer.
