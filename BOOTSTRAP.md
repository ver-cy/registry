# BOOTSTRAP

This file is the traversal entry point of the Vercy meta-model registry, per the ARCH-017 traversal and layout contract. Every walk of this repository, by a human or by an agent, starts here. It declares the reading order and the manifest of what lives where. Files not listed in the manifest are non-normative.

## What this repository is, in one paragraph

One git registry of meta-models where each entry is both a registry record and a node of the Meta-Model Dependency Graph (the MMDG), one edge file for the typed relationships between them, one resolver that turns a task into a bounded context pack, and CI that gates the write path. It is the running instance of the ELMM profile specified in ver-cy/elmm. Synchronization is `git pull`; there are no long-running services; the write path is a propose-only pull request.

## Reading order for humans

1. [README.md](README.md): what the registry is, why the registry and the MMDG are one artifact, the directory tour, the four-record seed and its edges, how to register a model, how the resolver works, and the walking-skeleton scope.
2. [entries/](entries/): the Model Registration Records. Read `vercy.aismm.yaml` first (the reference Core model and the template every registrant matches), then `vercy.apmm.yaml`, `vercy.plmm.yaml`, and `vercy.elmm.yaml`.
3. [mmdg/edges.json](mmdg/edges.json): the two seed edges. Read each edge beside the two entries it connects.
4. [schema/](schema/): the JSON Schemas (draft 2020-12), vendored from ver-cy/elmm. Read each schema beside the ELMM spec section that defines it.
5. [examples/](examples/): the worked task. Read the task descriptor, then the walkthrough, then the generated fixtures the walkthrough points at.
6. [CONTRIBUTING.md](CONTRIBUTING.md) before proposing any change.

## Reading order for agents

1. Parse this file for the manifest below.
2. Load every schema in `schema/` and validate every file in `entries/` against the ELMM node profile, its projected upstream field subset against the upstream registry-entry schema, and every record in `mmdg/edges.json` against the edge schema. A validation failure means the checkout is broken; stop and report.
3. Treat the SHALL statements in the ELMM specification (ver-cy/elmm) as the behavior contract. This repository is data plus one script; the normative text lives there.
4. Treat every enumeration of models as illustrative. The normative set is the contents of `entries/`, and the only normative identity is the registry `id` plus the Canonical Semantic Name and Namespace (ARCH-003), with version per ARCH-002 and the Semantic Fingerprint per ARCH-009.
5. When assembling context from this repository, apply the seven context rules: single anchor, minimal-sufficient, projections not objects, provenance plus pins, least privilege, no secrets, just-in-time dereference.
6. Never resolve mastership from the edge file. A `masters-link` edge is a pointer; the authority is the owning model's ARCH-018 `sources.yaml` register.
7. The resolver is deterministic. Timestamps come from CLI arguments or input fields, never from the wall clock; `snapshot_id` is derived by hashing the resolved set with the edges digest and the task reference. Do not introduce a clock or a random source into any executable path.

## Manifest: what lives where

| Path | Kind | What it is |
|---|---|---|
| `README.md` | doc | Front page: the registry-meets-MMDG thesis, directory tour, seed, resolver, scope |
| `BOOTSTRAP.md` | doc | This file: the ARCH-017 entry point, reading order, manifest |
| `CHANGELOG.md` | doc | Version history, Keep a Changelog format |
| `CONTRIBUTING.md` | doc | How to propose a registration; the propose-only ethos; the CI gate; one node per PR is fine |
| `LICENSE` | license | Apache License 2.0, full text |
| `entries/` | data | One Model Registration Record per registered model, `<id>.yaml`. Each is a registry entry and an MMDG node at once, validated against the ELMM node profile with its upstream field subset validated against the upstream `entry.schema.json` |
| `mmdg/edges.json` | data | The single edge file: an array of typed edge records (`composes`, `references`, `masters-link`, `deprecated-in-favor-of`) over the entries |
| `schema/` | schema | JSON Schemas (draft 2020-12), vendored from ver-cy/elmm: node profile, edge record, task descriptor, context pack, Twin Composition Snapshot |
| `resolver/` | code | `resolve.py`: the deterministic per-task resolver that emits a context pack and a Twin Composition Snapshot |
| `ci/` | code | The four fail-closed checks run on every pull request: schema validation, graph integrity, resolver determinism, and zero-change registration |
| `examples/` | example | One worked task end to end: `task-product-impact.json`, `walkthrough.md`, and the generated fixtures under `examples/expected/` |

## Traversal rules

- **Entry point.** This file is the single entry point. Tools that walk the repository start here and follow the manifest.
- **Identity.** Cross-model references carry a registry id and a version, or a Semantic Fingerprint. Registry ids are publisher-prefixed (`vercy.aismm`, `vercy.plmm`). Acronyms (AISMM, PLMM, APMM, ELMM) are display aliases only.
- **Two class fields.** `role` (`core | landscape | kernel`) is the MMDG-normative field; the upstream `kind` is mapped from it (`core` to `domain`, `landscape` and `kernel` to `enterprise`) and is retained for upstream tooling. The edge field `compositional_role` binds to ARCH-016 roles R1 to R8 and is distinct from the node `role`.
- **Edges.** The four edge types are `composes`, `references`, `masters-link`, `deprecated-in-favor-of`. `declared_min` is the sole resolver input under Minimal Version Selection; `version_range` is a publish-time V-gate predicate only. No `composes` or `references` edge leaves the kernel node.
- **Snapshots.** A resolved composition is pinned by a Twin Composition Snapshot, `{id, version, semantic_fingerprint}` per resolved model. The fingerprint is the semantic pin; `edges_hash` and `source_ref` are non-semantic transport-integrity fields.
- **Freshness.** Synchronization is `git pull`. Every record declares a `sync_contract` (`{mode, freshness}`); anything read into a context pack carries an `observed_at` stamp.
- **Mirrors.** The published repository is the System of Record for the registry contents; ver-cy/elmm is the System of Record for the schemas and the spec. Every copy elsewhere is a mirror.
