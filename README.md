# The Vercy meta-model registry

The single home where every meta-model registers as one node and declares its typed relationships to the others. One entry per model. One edge file for the graph between them. One resolver that turns a task into a bounded context pack. This repository is a walking skeleton in the sense of ver-cy/elmm: a git registry, a small edge file, one resolver script, one worked example, and CI checks, with no long-running services and a propose-only write path.

- **The specification** lives in [ver-cy/elmm](https://github.com/ver-cy/elmm): the ELMM profile, the JSON Schemas, and the normative SHALL text. This repository is the running instance of that profile.
- **Entry point for humans and agents:** [BOOTSTRAP.md](BOOTSTRAP.md), per the ARCH-017 traversal contract.
- **Status:** v0.1.0, Working Draft. **License:** Apache-2.0.

## What this repository is

Two things that used to be described as separate artifacts are the same artifact here. A registry lists the meta-models an organization has: who owns each one, where its authoritative source lives, what version is current, what license and access apply. A dependency graph records how those models relate: which Landscape composes which Core, which model references kinds another owns, which successor a deprecated model points at. In this repository those are one file each way. Every entry in `entries/` is at once a registry entry and a node of the Meta-Model Dependency Graph (the MMDG); every record in `mmdg/edges.json` is one typed edge between two of those nodes.

That convergence is the whole point. In the Vercy roadmap the unified registry (workstream B3) and the live MMDG (workstream B5) were drawn as two deliverables. They are not: a registry that carries no relationships is a spreadsheet, and a graph whose nodes are not the registered models is a diagram nobody maintains. This repository is where B3 meets B5. An entry file therefore answers to both schemas at once, the way the convergence requires. It carries the upstream Meta-Universe registry-entry fields (`id`, `name`, `publisher`, `owner`, `version`, `kind`, `status`, `license`, `access`, `purpose`, `registered`, and `source` when access is public) and the MMDG node-profile fields (`csn`, `primary_namespace`, `role`, `fingerprint`, `source`, `steward`, `sync_contract`, `exports`, `requires`, `display_alias`, and the optional `industry`, `origin`, `provenance`, `routing_hints`). CI validates the whole record against the ELMM node profile, the profile schema this repository runs, and it validates the record's projected upstream field subset against the unmodified upstream `entry.schema.json`. It validates a projection, not the whole file, against upstream on purpose: the upstream schema is `additionalProperties: false`, so the profile extension fields would be rejected if the full record were thrown at it. Those extension fields ride declared change requests upstream: `role` is CR-1, and `sync_contract`, `exports` and `requires` are CR-2; `csn`, `display_alias`, `industry`, `origin`, `provenance` and `routing_hints` are profile-local and the subject of no change request. When CR-1 and CR-2 are accepted the projection step falls away and the whole record validates against upstream directly. Both validations run on every pull request.

The two class fields sit side by side and answer different questions. `role` is the MMDG-normative field and holds the three-level triad `core | landscape | kernel`. `kind` is the upstream registry scope class and is mapped from `role`: `core` maps to `domain`, `landscape` and `kernel` both map to `enterprise`. When the two ever disagree, `role` governs composition and resolution; `kind` is retained only so the upstream registry tooling has a value it recognizes. Lifecycle `status` follows the same discipline. The ELMM node profile uses `active | deprecated | retired`; the upstream registry uses `draft | stable | deprecated | retired`. The seed records carry `active`, which corresponds to the upstream `stable` lifecycle for the projected upstream subset (a value-level change request filed alongside CR-1 and CR-2); `deprecated` and `retired` carry their ARCH-002 meaning identically in both. A record that reads as active resolves; a `deprecated` or `retired` record does not.

What this repository is **not**: it is not a copy of any model. Registration is discovery, not storage. An entry references an authoritative source (the ARCH-018 master) and never inlines it. The models keep their own repositories, their own owners, their own release cadence. The registry holds identity, relationships, and the resolver that reads them; nothing else.

## The directory tour

| Directory | What is inside |
|---|---|
| `entries/` | One YAML Model Registration Record per registered model, named `<id>.yaml` (for example `entries/vercy.plmm.yaml`). Each file is a registry entry and an MMDG node at once. |
| `mmdg/` | `edges.json`, the single edge file: an array of typed edge records over the entries. This is the graph. |
| `schema/` | The JSON Schemas (draft 2020-12) the entries and edges validate against, vendored from ver-cy/elmm: the node profile, the edge record, the task descriptor, the context pack, and the Twin Composition Snapshot. Vendored so a checkout validates offline; ver-cy/elmm remains the System of Record for the schema text. |
| `resolver/` | One resolver script, `resolve.py`, invoked per task. It reads `entries/` and `mmdg/edges.json`, walks the graph, runs Minimal Version Selection, and emits a context pack and a Twin Composition Snapshot. Python 3, standard library plus PyYAML and jsonschema, deterministic, no wall-clock and no network at resolve time. |
| `ci/` | The four fail-closed checks that run on every pull request: schema validation, graph integrity, resolver determinism, and zero-change registration. |
| `examples/` | One worked task end to end: the task descriptor, a narrated walkthrough, and the generated fixtures the resolver produces from it. |

## The seed: four records and the edges

The v0.1 seed registers exactly what exists, not the fourteen Core models and eleven Landscapes any illustrative enumeration might list. Four active records and two edges.

| Entry | `role` | `kind` | Version | Access | Origin | What it demonstrates |
|---|---|---|---|---|---|---|
| `entries/orkestron.aismm.yaml` | core | domain | 3.1.0 | public | external | The reference Core model, registered from an outside publisher at `github.com/orkestron-ai/software-meta-model`. Ships the template every registrant matches. |
| `entries/vercy.apmm.yaml` | core | domain | 0.1.0 | public | internal | The second Core model, proving the non-software case. Its substance derives from a restricted-access source specification recorded as provenance, with no link; exactly one node exists for it. |
| `entries/vercy.plmm.yaml` | landscape | enterprise | 0.2.0 | public | internal | The single Landscape: composes AISMM, references APMM, and declares the routing hints the resolver matches. |
| `entries/vercy.elmm.yaml` | kernel | enterprise | 0.1.0 | public | internal | The kernel, registered under its own versioning discipline, with empty `requires` and no outgoing edges. Its knowledge of every node comes from the registry, not from graph edges. |

The seed is these four active models. Every enumeration of models anywhere in Vercy documentation is illustrative and non-normative. The normative set of models is whatever this registry holds at the time.

### The MMDG as an ASCII diagram

```text
  Level 3 (kernel)     vercy.elmm
                       Registers nodes, validates edges, resolves
                       compositions. Holds NO composes or references
                       edges of its own; its knowledge of every node
                       comes from the registry, not from graph edges.

  Level 2 (landscape)  vercy.plmm
                        |                        \
                composes |                          \ references
                R2       |                            \ R4  (kinds: role, task)
                (min 3.1.0)                            (min 0.1.0)
                        v                                v
  Level 1 (core)  orkestron.aismm                   vercy.apmm

  Two edges in mmdg/edges.json:
    1. vercy.plmm  composes    orkestron.aismm  (R2, declared_min 3.1.0, kinds software-product, entity)
    2. vercy.plmm  references  vercy.apmm       (R4, declared_min 0.1.0, kinds role, task)

  No composes or references edge leaves the kernel node. A shared Core
  model is registered once and composed by many Landscapes without
  duplication. The graph is directed and acyclic on composes.
```

The edge vocabulary is closed and exactly four types: `composes` (a Landscape orchestrates a Core model by reference, never by inclusion, per an ARCH-016 mechanism named in `compositional_role`), `references` (a model refers to kinds declared in the target's `exports`, named in the edge's `kinds`), `masters-link` (a pointer into the owning model's ARCH-018 mastership register, never a free restatement of mastership as graph data), and `deprecated-in-favor-of` (the ARCH-002 successor pointer on a deprecated model). The seed exercises two of the four (`composes` and `references`); `masters-link` and `deprecated-in-favor-of` are in the vocabulary but not drawn in this minimal graph.

## How to register a new model

The write path is a governed proposal. There is no other way in.

1. **Open a pull request** that adds `entries/<id>.yaml` for the new model and, if the model relates to any already-registered model, the matching edge records in `mmdg/edges.json`. One node per pull request is fine and encouraged; a small, reviewable change is the norm, not a defect.
2. **Fill the record** so it satisfies both schemas. The upstream fields (`id`, `name`, `publisher`, `owner`, `version`, `kind`, `status`, `license`, `access`, `purpose`, `registered`, and `source` when `access` is `public`) plus the profile fields (`csn`, `primary_namespace`, `role`, `fingerprint`, `steward`, `sync_contract`, `exports`, `requires`, `display_alias`, and the optional `industry`, `origin`, `provenance`, `routing_hints`). Map `kind` from `role` as described above. Identity is the registry `id` plus the Canonical Semantic Name and Namespace (ARCH-003); the semantic pin is the Semantic Fingerprint (ARCH-009), never a byte hash.
3. **Declare relationships honestly.** Every kind the model references appears in some target's `exports`, and every `requires` entry names a foreign model, a referenced kind, and the minimum version the reference was validated against. Each `requires` `min_version` equals the `declared_min` of the corresponding edge; CI enforces the agreement.
4. **CI validates** the proposal, fail-closed, in four checks: schema validation of every record and edge; graph integrity (referential integrity of both endpoints of every edge, export coverage of every kind a `references` edge names, agreement between each `requires` minimum and the corresponding edge `declared_min`, acyclicity of `composes`, kernel isolation, and unique registry ids); resolver determinism and output validity; and the zero-change registration check. A red check blocks merge, no exceptions. Humans enter only for ARCH-014 scope escalations.
5. **The write path defaults to PROPOSE.** The registry never masters domain data. Merging an entry publishes a discovery record that points at a source the registry does not own; it does not copy or modify the model. Direct mutation of any mastered source is out of scope for this repository entirely.

Registering a model is thus a data change reviewed like any other, which is the whole governance story of v0.1: governance that is not on the write path does not exist, so the write path is a pull request and the admission gate is CI.

## How the resolver turns a task into a bounded context pack

At runtime the registry is a semantic router. A task descriptor goes in; a context pack comes out, sized to a token budget and consumed directly by the calling agent harness. `resolver/resolve.py` is invoked per task, reads the registry at a pinned commit, and runs the five-step algorithm the ELMM spec fixes (section 8.2):

1. **Route by declared hints.** Match the descriptor's `referenced_entities` and `purpose` against the `routing_hints` declared by Landscape and Core records: a hint matches when a `referenced_entities` entry appears in a record's `match_entities`, or the `purpose` contains one of its `match_purpose_keywords`. The matches form the anchor set. In v0.1 this is the only routing stage.
2. **Walk the graph.** Take the transitive closure of `composes` and `references` edges out of the anchor set. This is how a task that names only `plmm.product` pulls in AISMM and APMM: the resolver discovers them by walking PLMM's own edges, not because the task named them.
3. **Select versions by Minimal Version Selection.** `declared_min` on the edges is the sole resolver input. For each model major identity, take the maximum of the declared minimums on participating incoming edges; an anchor with no participating incoming edge resolves to its registered version. Exactly one live instance per major identity. Major versions are distinct identities and may coexist. Declared ranges are publish-time V-gate predicates only and never enter the resolver.
4. **Pin at the declared ref.** Read each resolved model's pinned `source.ref` and its declared Semantic Fingerprint (ARCH-009) from the registration record, and stamp `observed_at` from the resolver input. The v0.1 skeleton opens no source repository and recomputes no fingerprint at resolve time; the live fetch and recompute named in the spec algorithm is deferred. Compare `observed_at` against the record's declared `sync_contract` freshness; a source older than its freshness is flagged in the coverage statement, not fatal.
5. **Assemble.** Build one member projection per anchored Meta-Object (each satisfying the CORE-009 single-object rule), enforce `max_tokens`, and emit the context pack and the Twin Composition Snapshot.

The pack obeys seven context rules: single anchor, minimal-sufficient content, projections not objects, provenance plus version pins, least privilege, no secrets, just-in-time dereference. The single economic parameter is `max_tokens`; when the assembled members exceed it, the resolver degrades members to summary form and records the degradation in the coverage statement. Version pins carry the Semantic Fingerprint, never a byte hash. The Twin Composition Snapshot is the lockfile: replaying it rebuilds the same pack, and it answers which model versions were live at a given time.

The resolver is deterministic by construction. It reads no wall clock and hits no network at resolve time: any timestamp (`observed_at`, `created_at`) comes from a CLI argument or a field in the input, and `snapshot_id` is derived by hashing the resolved set together with the edges digest and the task reference. The same inputs produce byte-identical outputs on every machine forever, which is what lets CI regenerate the example fixtures and diff them.

## The walking-skeleton scope, and what is deferred

This repository is the minimal thing one organization could run in weeks, and the floor is stated so nobody gold-plates it: one git registry with CI, one resolver script, zero long-running services. No control plane, no admission webhook service, no subscription bus, no protocol server, no reconciliation controllers. Synchronization in v0.1 is `git pull` at resolve time. The durable component is the git repository; every derived artifact (context packs, snapshots) is rebuildable from it.

What is deliberately deferred, with triggers rather than dates (per the ELMM spec Deferrals and the dossier deferral list):

- **v0.2, on a second real consumer or a third registered model:** a protocol facade whose tools are the router verbs, snapshot automation on every resolve, a push-webhook change event (not a bus), the live fetch and fingerprint recompute at resolve time, and the completed Landscape rewrite.
- **v1.0, on the first model mastered outside git:** reconciliation loops with `observed_at` on every node, per-attribute mastership and precedence under ARCH-018, mapping sets in the SSSOM shape, a kernel conformance suite, and delta subscriptions.
- **Indefinite, on a named failure the skeleton cannot absorb:** publish-time satisfiability proofs, signed provenance, a general graph query language (ISO/IEC 39075 GQL is the standard to track), node-level bitemporality, and degradation ladders beyond `max_tokens`.

No deferred item accrues normative weight before its trigger fires. Navigation in v0.1 is transitive closure along typed edges (ARCH-017), which answers every current question including the flagship impact query.

## Relationship to the rest of the ecosystem

| Repository or standard | Relationship |
|---|---|
| [ver-cy/elmm](https://github.com/ver-cy/elmm) | The specification. This repository is the running instance of the ELMM profile: the schemas here are vendored from it, and its SHALL text is the behavior contract the resolver and CI implement. |
| [ver-cy/plmm](https://github.com/ver-cy/plmm) | The Product Landscape Meta-Model, the single Landscape in the seed. It is registered here as `vercy.plmm`; it composes AISMM and references APMM. |
| [ver-cy/world-models](https://github.com/ver-cy/world-models) | The neutral catalogue of meta-model cards. Any of its models can register here as a Core model by adding one entry file and its edges; that path is the point of the zero-change registration guarantee. |
| [ver-cy/meta-universe](https://github.com/ver-cy/meta-universe) | The Meta-Universe standard, the substrate. Every mechanism this registry relies on is bound by reference to it (ARCH-002 versioning, ARCH-003 identity, ARCH-009 fingerprint, ARCH-014 policy, ARCH-016 composition, ARCH-017 traversal, ARCH-018 mastership, CORE-009 and CORE-012 projection, V0 to V5 gates, FED-013 discovery). The registry adds no parallel machinery; it profiles the upstream `entry.schema.json` and lets the MMDG edge record be the one genuinely new artifact. |

## Status and versioning

- **Current version:** v0.1.0, Working Draft. See [CHANGELOG.md](CHANGELOG.md).
- Versioning follows ARCH-002. Major versions of any registered model are distinct registry identities that may coexist during migration.
- Contributions follow [CONTRIBUTING.md](CONTRIBUTING.md): one proposal per pull request, CI must pass, decisions the ELMM spec marks adopted are not reopened by pull request.
- License: Apache-2.0. See [LICENSE](LICENSE).
