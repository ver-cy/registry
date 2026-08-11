# The Vercy meta-model registry

The single home where every meta-model registers as one node and declares its typed relationships to the others. One entry per model. One edge file for the graph between them. One resolver that turns a task into a bounded context pack. This repository is a walking skeleton in the sense of ver-cy/elmm: a git registry, a small edge file, one resolver script, one worked example, and CI checks, with no long-running services and a propose-only write path.

- **The specification** lives in [ver-cy/elmm](https://github.com/ver-cy/elmm): the ELMM profile, the JSON Schemas, and the normative SHALL text. This repository is the running instance of that profile.
- **Entry point for humans and agents:** [BOOTSTRAP.md](BOOTSTRAP.md), per the ARCH-017 traversal contract.
- **Status:** v0.3.0, Working Draft. **License:** Apache-2.0.

## What this repository is

Two things that used to be described as separate artifacts are the same artifact here. A registry lists the meta-models an organization has: who owns each one, where its authoritative source lives, what version is current, what license and access apply. A dependency graph records how those models relate: which Landscape composes which Core, which model references kinds another owns, which successor a deprecated model points at. In this repository those are one file each way. Every entry in `entries/` is at once a registry entry and a node of the Meta-Model Dependency Graph (the MMDG); every record in `mmdg/edges.json` is one typed edge between two of those nodes.

That convergence is the whole point. In the Vercy roadmap the unified registry (workstream B3) and the live MMDG (workstream B5) were drawn as two deliverables. They are not: a registry that carries no relationships is a spreadsheet, and a graph whose nodes are not the registered models is a diagram nobody maintains. This repository is where B3 meets B5. An entry file therefore answers to both schemas at once, the way the convergence requires. It carries the upstream Meta-Universe registry-entry fields (`id`, `name`, `publisher`, `owner`, `version`, `kind`, `status`, `license`, `access`, `purpose`, `registered`, and `source` when access is public) and the MMDG node-profile fields (`csn`, `primary_namespace`, `role`, `fingerprint`, `source`, `steward`, `sync_contract`, `exports`, `requires`, `display_alias`, and the optional `industry`, `origin`, `provenance`, `routing_hints`). CI validates the whole record against the ELMM node profile, the profile schema this repository runs, and it validates the record's projected upstream field subset against the unmodified upstream `entry.schema.json`. It validates a projection, not the whole file, against upstream on purpose: the upstream schema is `additionalProperties: false`, so the profile extension fields would be rejected if the full record were thrown at it. Those extension fields ride declared change requests upstream: `role` is CR-1, and `sync_contract`, `exports` and `requires` are CR-2; `csn`, `display_alias`, `industry`, `origin`, `provenance` and `routing_hints` are profile-local and the subject of no change request. When CR-1 and CR-2 are accepted the projection step falls away and the whole record validates against upstream directly. Both validations run on every pull request.

The two class fields sit side by side and answer different questions. `role` is the MMDG-normative field and holds the three-level triad `core | landscape | kernel`. `kind` is the upstream registry scope class and is mapped from `role`: `core` maps to `domain`, `landscape` and `kernel` both map to `enterprise`. When the two ever disagree, `role` governs composition and resolution; `kind` is retained only so the upstream registry tooling has a value it recognizes. Lifecycle `status` follows the same discipline. The ELMM node profile uses `active | deprecated | retired`; the upstream registry uses `draft | stable | deprecated | retired`. The seed records carry `active`, which corresponds to the upstream `stable` lifecycle for the projected upstream subset (a value-level change request filed alongside CR-1 and CR-2); `deprecated` and `retired` carry their ARCH-002 meaning identically in both. A record that reads as active resolves; a `deprecated` or `retired` record does not.

What this repository is **not**: it is not a copy of any model. Registration is discovery, not storage. An entry references an authoritative source (the ARCH-018 master) and never inlines it. The models keep their own repositories, their own owners, their own release cadence. The registry holds identity, relationships, and the resolver that reads them; nothing else.

## Two entry classes, two orthogonal facet axes

Everything above describes the internal meta-models: the MMDG nodes, few and governed. As of v0.2 the repository is a unified registry with a second entry class alongside them, and two facet axes that classify both classes the same way.

**The two entry classes.** An **internal meta-model** is an MMDG node: a governed, versioned model with one YAML record in `entries/`, joined to the others by typed edges. There are ten of them: seven governed meta-models (`orkestron.aismm`, `vercy.apmm`, `vercy.ccmm`, `vercy.oumm`, `vercy.collmm`, `vercy.plmm`, `vercy.elmm`) and three illustrative tenant instance nodes registered the same way (`acme.fhir`, `deploy.aismm-product`, `deploy.portfolio`). An **external standard** is a discoverable reference: one row in `external/external-standards.csv`, one of 1180 reference standards the world already publishes. The difference is not cosmetic. Internal nodes are in the graph; external standards are not. An external standard is a citation the registry can find and facet, never a node the resolver walks. It becomes an MMDG node only when it is instantiated by the external-to-internal transform (workstream B6), described below. Until then the two classes share the facet axes but nothing else: external standards carry no `role`, no `exports`, no `requires`, no edges, and the resolver never sees them.

**The two axes are orthogonal, and both apply to both classes.** They answer different questions:

- **Cluster: what a thing is.** The ontological kind of the entity, one of the fifteen clusters of the world-models corpus (`activity-work`, `built-environment`, `civilization`, `economy`, `events-phenomena`, `flows-resources`, `knowledge-information`, `matter-artifacts`, `organizations`, `people-groups`, `planet-nature`, `polity`, `registries-ledgers`, `security-ownership-access`, `society`). Cluster is the primary facet for internal meta-models and an optional facet for external standards in v0.2.
- **Industry: which sector uses or governs it.** The sector of activity, drawn from the `vercy-industry` vocabulary: fifteen ISIC Rev.4 aligned verticals plus twelve cross-cutting horizontals, twenty-seven codes in all, multi-valued per entry. Every external standard inherits its industry codes from its Group; every internal meta-model declares its own in its entry file.

The axes are independent by construction. A geospatial coordinate reference system is the same kind of thing (its cluster is fixed) whether it is applied in agriculture, aviation, or government (its industry set varies). And State and Polity is one vertical among many (`government-public-sector`) and one cluster among fifteen (`polity`), never a privileged frame: the registry treats the state as one domain of activity, not the axis the rest hangs from.

### The facet vocabularies

The controlled vocabularies live under `facets/`, and entries reference codes by scheme id so a vocabulary can be re-mapped without a schema change:

| File | Scheme | What it is |
|---|---|---|
| `facets/clusters.yaml` | `vercy-cluster` | The fifteen ontological clusters. The "what a thing is" axis. Each code is the exact world-models directory id, so a cluster code resolves to its corpus home. |
| `facets/industry.yaml` | `vercy-industry` | The fifteen ISIC-aligned verticals and twelve horizontals. The "which sector" axis. ISIC alignment is for neutrality (NACE, NAICS and GICS map onto ISIC); the vocabulary is swappable. |
| `facets/group-industry-map.csv` | | Maps each of the 37 external-registry Groups to one or more industry codes. This is how external standards inherit industry from their Group, assigned once per Group rather than per row. |
| `facets/compositional-roles.yaml` | `vercy-compositional-role` | The eight ARCH-016 compositional roles R1 to R8, each with its default link type and catalogue count. The role definitions are bound by reference to ARCH-016; this file is the single materialized vocabulary for them. |
| `facets/link-types.yaml` | `vercy-link-type` | The ARCH-016 composition mechanisms (`EMBED`, `REFERENCE`, `MIX-IN`, `COMPOSE`, `ALIGN`, `EXTEND`) plus the literal `N/A`. |

The last two vocabularies describe how a standard would compose, not what it is or which sector owns it. That classification is informative guidance: a role suggests a default link type, but an actual link is settled by the instantiation transform, not asserted here.

### The external standards catalogue

`external/external-standards.csv` is the discovery catalogue, generated, never hand-edited. It is `external/external-models.source.csv` (1180 authored rows, fifteen fixed columns) with two facet columns appended: `Origin` (the constant `external` for every row, so the origin facet reads uniformly across both classes) and `Industry` (the semicolon-joined vercy-industry codes inherited from the row's Group). The source rows also carry each standard's ARCH-016 `CompositionalRole` (R1 to R8) and `DefaultLinkType`, so the catalogue is queryable by how a standard would compose as well as by what sector uses it. See `external/README.md` for the column-by-column account. Each generated row validates against `schema/external-standard.schema.json`, a schema that is deliberately distinct from the internal node schema and carries none of the MMDG node profile: a reference is not a node, and the schemas say so.

### Tooling: import, build_index, query

Three small tools under `tools/`, each Python 3 (standard library plus PyYAML), each locating the registry root from its own file location, each deterministic (stable sort order, fixed dialects, no wall clock, no randomness), so every regenerated artifact is byte-identical:

```
external-models.source.csv + facets/group-industry-map.csv
              |  tools/import_external.py
              v
     external/external-standards.csv        (source columns + Origin + Industry)
              |
              |  entries/*.yaml  +  facets/*
              v  tools/build_index.py
        index/unified-index.json            (one faceted index over BOTH classes)
              |
              |  tools/query.py
              v
        answers to facet queries
```

- `tools/import_external.py` builds the external catalogue. It fails closed if a source Group is missing from the Group map or a mapped code is not a known industry code.
- `tools/build_index.py` builds `index/unified-index.json`, the single index that joins the ten internal nodes and the 1180 external standards into one structure keyed by the shared facets, so both classes are searchable together.
- `tools/query.py` reads that index and answers facet queries. Representative invocations, with the query dimensions being cluster, industry, origin, and entry class:

```
python tools/import_external.py                          # regenerate the external catalogue
python tools/build_index.py                              # regenerate the unified index
python tools/query.py --cluster organizations            # every entry whose cluster is organizations
python tools/query.py --industry financial-services      # everything in the financial-services sector
python tools/query.py --origin internal --cluster organizations  # internal entries of one cluster
python tools/query.py --industry government-public-sector # the state as one sector among many
```

### The unified index

`index/unified-index.json` is the generated join over both entry classes: the ten internal nodes and the 1180 external standards, indexed by the shared facet axes (cluster, industry) plus origin, and, for external standards, the ARCH-016 compositional role (R1 to R8). The internal core, landscape, and kernel node role is not indexed in v0.2; it lives in the entry files and is walked by the resolver, not queried through this index. It is what makes "show me everything in this sector" or "show me every entry of this ontological kind" a single lookup that crosses the internal/external boundary, while the index still records which class each entry belongs to so a consumer never mistakes a reference for a node. Like the catalogue, it is generated and byte-comparable, never authored by hand.

### How CI guards it

The v0.1 admission gate keeps its four fail-closed checks unchanged (schema, graph, resolver, zero-change). v0.2 adds a fifth, `ci/check_facets.py`, wired into `ci/run.py`, that guards the facet layer: every industry and cluster code on an internal entry is in its vocabulary; every Group in the source catalogue is covered by the Group map and every mapped code is known; the external catalogue regenerates byte-identical and each row validates against `schema/external-standard.schema.json`; and the unified index regenerates byte-identical. A drifted vocabulary, an unmapped Group, a hand-edit of a generated file, or a non-deterministic tool all fail the gate. The numbers the gate protects: 10 internal nodes and 9 edges; 1180 external standards across 37 Groups; 15 clusters and 27 industry codes (15 verticals plus 12 horizontals); the eight ARCH-016 roles distributed R1 9, R2 156, R3 67, R4 140, R5 55, R6 263, R7 22, R8 468.

## The external-to-internal transform (B6)

Everything above stops at the boundary: an external standard is a reference the registry can find and facet, never a node the resolver walks. The external-to-internal transform (workstream B6) is the single operation that crosses that boundary. It takes one external standard, one row of `external/external-standards.csv`, and instantiates an internal tenant meta-model from it: a new Model Registration Record that is a first-class MMDG node the resolver can compose, plus an instantiation manifest that records exactly how the crossing was made. It is the flagship button, and it is one command.

The operation is a composition of machinery this repository already binds by reference, stated by the owner as a formula:

> external-to-internal = Extension-Model + Policy-Consistency + Data-Mastership

made a single operation. `Extension-Model` supplies the binding (adopt the external model by reference, never by silent copy), `Policy-Consistency` (ARCH-014) supplies the governance overlay, and `Data-Mastership` (ARCH-018) fixes who owns the data. The composition mechanism is ARCH-016 (`Meta-Model-Composition`), the same ARCH-016 roles R1 to R8 the facet layer already carries. The transform adds no new theory; it wires the four together and runs them once.

What the overlay does, in the order the generated record carries it:

- **Binds the external model.** The generated entry carries an AISMM `external_binding` block (the established shape: `target`, `composition_kind`, `link_type`, `standard_id`, `version`, bound by reference to the AISMM external-model-binding governance and its schema in the AISMM repository). The `link_type` is derived from the standard's `DefaultLinkType` and the `composition_kind` from its `CompositionalRole` (R1 to R8, ARCH-016), with the AISMM conditional that a `value_object` forces `link_type` `embed`. The registry classification of the standard is therefore what settles the binding, deterministically.
- **Overlays the ver.cy policy profile.** The default profile is `transform/policy-profiles/vercy-baseline.yaml`: the eight invariant controls of the Common Operating Law, IC-1 to IC-8, overlaid on the new model, and Policy-Consistency (ARCH-014) as the discipline that keeps them coherent. Two controls carry the weight. IC-1 (one master per dataset, mastership declared in the Mastership Register, never inferred) is why the transform declares mastership rather than leaving it implied. IC-3 (data is never a command: every context section carries an origin taint class) is why an instantiated external model is `mirrored-external`, therefore data, never instructions. A fresh instantiation starts at delegation tier T1 (human-in-the-loop): the transform proposes, a human approves.
- **Declares data-mastership.** Per ARCH-018 the external source is the master. The generated entry's `source.repository` points at the standard's `SpecificationSourceURL`, the authoritative source the registry does not own, and the manifest records a Mastership Register stanza whose system of record is that external source, with an inbound flow direction. The registry masters identity and relationships; it never masters the external model.
- **Records lineage.** Per `Provenance-Graph` the manifest records `derived_from` (the external standard), the transform that produced the node, and a provenance note, so the crossing is auditable back to its source.

**Worked example.** Instantiate HL7 FHIR for tenant `acme`:

```
python tools/instantiate.py --standard FHIR --tenant acme --at 2026-08-10T00:00:00Z
```

FHIR is classified `R4` / `REFERENCE` in the catalogue, so the binding resolves deterministically to `composition_kind` `entity` and `link_type` `reference` (no value-object override applies); the `healthcare-life-sciences` industry facet is inherited from the row verbatim; and `source.repository` is the FHIR specification URL, the master per ARCH-018. Running it produces exactly two artifacts:

1. **An entry** under `entries/` (for example `entries/acme.fhir.yaml`): the new internal Model Registration Record, `kind` domain, `role` core, `origin` internal, `status` draft, `version` 0.1.0, stewarded by the tenant, validating against `schema/registry-node.schema.json` at v0.3 with the new `derived_from`, `external_binding`, `applied_policies` and `tenant` fields filled. Once written it is an MMDG node: `tools/build_index.py` indexes it and the resolver can compose it.
2. **A manifest** under `instantiations/` (one JSON file per instantiation): the full transform result, recording the `external_ref`, the `internal_id` of the new entry, the `external_binding` block emitted, the `mastership` stanza (system of record set to the external source), the `applied_policies` (the IC controls and profile policies overlaid), the `delegation_tier` (T1 for a fresh instantiation), the `lineage`, and the deterministic `semantic_fingerprint`. It validates against `schema/instantiation-manifest.schema.json`.

The transform is deterministic and CI-guarded. It reads no wall clock (the timestamp comes from the `--at` ISO-8601 argument) and no randomness: the `instantiation_id` and `semantic_fingerprint` are deterministic hashes over canonical content, and re-running with the same inputs yields a byte-identical entry and manifest. `ci/check_instantiations.py`, wired into `ci/run.py` after `check_facets`, is a fail-closed check that regenerates each committed instantiation and diffs it, validates every generated entry against the v0.3 node schema and every manifest against the manifest schema, and confirms the five prior checks still pass on the enlarged registry. The worked-example entry and manifest are not hand-written: they are generated by running the tool and committed as fixtures by the operator, so the example above is reproducible byte for byte.

The normative account is `transform/EXTERNAL-TO-INTERNAL.md`; the default overlay is `transform/policy-profiles/vercy-baseline.yaml`; the manifest shape is `schema/instantiation-manifest.schema.json`. This is the moment an external reference is promoted into the graph, the crossing the unified-registry section named and deferred.

## The directory tour

| Directory | What is inside |
|---|---|
| `entries/` | One YAML Model Registration Record per registered model, named `<id>.yaml` (for example `entries/vercy.plmm.yaml`). Each file is a registry entry and an MMDG node at once. |
| `mmdg/` | `edges.json`, the single edge file: an array of typed edge records over the entries. This is the graph. |
| `schema/` | The JSON Schemas (draft 2020-12) the entries and edges validate against, vendored from ver-cy/elmm: the node profile, the edge record, the task descriptor, the context pack, and the Twin Composition Snapshot. Vendored so a checkout validates offline; ver-cy/elmm remains the System of Record for the schema text. |
| `resolver/` | One resolver script, `resolve.py`, invoked per task. It reads `entries/` and `mmdg/edges.json`, walks the graph, runs Minimal Version Selection, and emits a context pack and a Twin Composition Snapshot. Python 3, standard library plus PyYAML and jsonschema, deterministic, no wall-clock and no network at resolve time. |
| `ci/` | The four fail-closed checks that run on every pull request: schema validation, graph integrity, resolver determinism, and zero-change registration. |
| `examples/` | One worked task end to end: the task descriptor, a narrated walkthrough, and the generated fixtures the resolver produces from it. |
| `facets/` | The controlled facet vocabularies: `clusters.yaml` and `industry.yaml` (the two axes), `group-industry-map.csv` (Group to industry), and `compositional-roles.yaml` and `link-types.yaml` (how an external standard would compose). |
| `external/` | The external standards discovery catalogue: `external-models.source.csv` (authored source), `external-standards.csv` (generated, source columns plus `Origin` and `Industry`), and `README.md`. References, not graph nodes. |
| `tools/` | The deterministic build and query tools: `import_external.py` (build the catalogue), `build_index.py` (build the unified index), `query.py` (facet queries), and `instantiate.py` (the external-to-internal transform, the B6 button). |
| `index/` | `unified-index.json`, the generated join over both entry classes keyed by the shared facets. Rebuildable from the entries, the catalogue and the vocabularies. |
| `transform/` | The external-to-internal transform: `EXTERNAL-TO-INTERNAL.md` (the normative spec), `policy-profiles/vercy-baseline.yaml` (the default ver.cy overlay: IC-1 to IC-8, T1 default, the mastership stance), and its `README.md`. |
| `instantiations/` | One JSON instantiation manifest per external-to-internal instantiation, recording how the external model was bound, which policies were overlaid, who masters the data, and the lineage. Generated by `tools/instantiate.py`, validated against `schema/instantiation-manifest.schema.json`. |

## The registered nodes and the edges

The registry registers exactly what exists, not the fourteen Core models and eleven Landscapes any illustrative enumeration might list. Ten nodes and nine edges: seven governed meta-models, three illustrative tenant instance nodes, and the nine typed edges between them.

| Entry | `role` | `kind` | Version | Access | Origin | What it demonstrates |
|---|---|---|---|---|---|---|
| `entries/orkestron.aismm.yaml` | core | domain | 3.1.0 | public | external | The reference Core model, registered from an outside publisher at `github.com/orkestron-ai/software-meta-model`. Ships the template every registrant matches. |
| `entries/vercy.apmm.yaml` | core | domain | 0.1.0 | public | internal | The second Core model, proving the non-software case. Its substance derives from a restricted-access source specification recorded as provenance, with no link; exactly one node exists for it. |
| `entries/vercy.ccmm.yaml` | core | domain | 0.1.0 | public | internal | The Context-Chain Core model: the layered context an agent operates inside. References APMM (role, knowledge-item) and OUMM (org-unit) rather than re-defining them. |
| `entries/vercy.oumm.yaml` | core | domain | 0.1.0 | public | internal | The org-unit primitive that other models resolve to rather than re-define. The shared reference target: PLMM, CCMM, CollMM and `deploy.portfolio` all reference its `org-unit` kind. |
| `entries/vercy.collmm.yaml` | core | domain | 0.1.0 | public | internal | The Collective Core model: the team that builds a product. References OUMM (org-unit) for its parent unit and seats. |
| `entries/vercy.plmm.yaml` | landscape | enterprise | 0.2.0 | public | internal | The single governed Landscape: composes AISMM, references APMM, OUMM and CollMM, and declares the routing hints the resolver matches. |
| `entries/vercy.elmm.yaml` | kernel | enterprise | 0.1.0 | public | internal | The kernel, registered under its own versioning discipline, with empty `requires` and no outgoing edges. Its knowledge of every node comes from the registry, not from graph edges. |
| `entries/acme.fhir.yaml` | core | domain | 0.1.0 | public | internal (tenant `acme`) | An illustrative B6 instantiation from an external standard. An isolated node with empty `exports` and no edges. |
| `entries/deploy.aismm-product.yaml` | core | domain | 0.1.0 | public | internal (tenant `deploy`) | An illustrative product software model at a deployment site. A `composes` target; exports `software-product` and `entity`. |
| `entries/deploy.portfolio.yaml` | landscape | enterprise | 0.1.0 | public | internal (tenant `deploy`) | An illustrative portfolio at a deployment site. Composes `deploy.aismm-product` and references OUMM, closing AISMM to PLMM at instance grain. |

The seven governed meta-models and the three illustrative tenant instances are what this registry holds. Every enumeration of models anywhere in Vercy documentation is illustrative and non-normative. The normative set of models is whatever this registry holds at the time.

### The MMDG as an ASCII diagram

```text
  Level 3 (kernel)      vercy.elmm
                        Registers nodes, validates edges, resolves compositions.
                        Holds NO composes or references edges of its own; its
                        knowledge of every node comes from the registry, not
                        from graph edges.

  Level 2 (landscape)   vercy.plmm                    deploy.portfolio
                          composes ->  orkestron.aismm   composes ->  deploy.aismm-product
                          references -> vercy.apmm        references -> vercy.oumm
                          references -> vercy.oumm
                          references -> vercy.collmm

  Level 1 (core)        orkestron.aismm   vercy.apmm   vercy.oumm   deploy.aismm-product
                        vercy.ccmm  references -> vercy.apmm, vercy.oumm
                        vercy.collmm references -> vercy.oumm
                        acme.fhir   (isolated node, empty exports, no edges)

  vercy.oumm is the shared org-unit primitive: vercy.plmm, vercy.ccmm,
  vercy.collmm and deploy.portfolio all reference its org-unit kind without
  re-defining it.

  Nine edges in mmdg/edges.json:
    1. vercy.plmm       composes    orkestron.aismm       (R2, declared_min 3.1.0, kinds software-product, entity)
    2. vercy.plmm       references  vercy.apmm            (R4, declared_min 0.1.0, kinds role, task)
    3. vercy.plmm       references  vercy.oumm            (R4, declared_min 0.1.0, kinds org-unit)
    4. vercy.plmm       references  vercy.collmm          (R4, declared_min 0.1.0, kinds collective)
    5. vercy.ccmm       references  vercy.apmm            (R4, declared_min 0.1.0, kinds role, knowledge-item)
    6. vercy.ccmm       references  vercy.oumm            (R4, declared_min 0.1.0, kinds org-unit)
    7. vercy.collmm     references  vercy.oumm            (R4, declared_min 0.1.0, kinds org-unit)
    8. deploy.portfolio composes    deploy.aismm-product  (R2, declared_min 0.1.0, kinds software-product, entity)
    9. deploy.portfolio references  vercy.oumm            (R4, declared_min 0.1.0, kinds org-unit)

  No composes or references edge leaves the kernel node, and acme.fhir
  carries none. A shared Core model is registered once and referenced or
  composed by many nodes without duplication. The graph is directed and
  acyclic on composes.
```

The edge vocabulary is closed and exactly four types: `composes` (a Landscape orchestrates a Core model by reference, never by inclusion, per an ARCH-016 mechanism named in `compositional_role`), `references` (a model refers to kinds declared in the target's `exports`, named in the edge's `kinds`), `masters-link` (a pointer into the owning model's ARCH-018 mastership register, never a free restatement of mastership as graph data), and `deprecated-in-favor-of` (the ARCH-002 successor pointer on a deprecated model). The graph exercises two of the four (`composes` and `references`); `masters-link` and `deprecated-in-favor-of` are in the vocabulary but not drawn in this graph.

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

- **A later minor release (the next resolver milestone), on a second real consumer or a third registered model:** a protocol facade whose tools are the router verbs, snapshot automation on every resolve, a push-webhook change event (not a bus), the live fetch and fingerprint recompute at resolve time, and the completed Landscape rewrite. The v0.2.0 release delivered the unified-registry facet layer and the v0.3.0 release delivered the external-to-internal transform, both described above; these resolver-facing items remain deferred.
- **v1.0, on the first model mastered outside git:** reconciliation loops with `observed_at` on every node, per-attribute mastership and precedence under ARCH-018, mapping sets in the SSSOM shape, a kernel conformance suite, and delta subscriptions.
- **Indefinite, on a named failure the skeleton cannot absorb:** publish-time satisfiability proofs, signed provenance, a general graph query language (ISO/IEC 39075 GQL is the standard to track), node-level bitemporality, and degradation ladders beyond `max_tokens`.

No deferred item accrues normative weight before its trigger fires. Navigation in v0.1 is transitive closure along typed edges (ARCH-017), which answers every current question including the flagship impact query.

## Relationship to the rest of the ecosystem

| Repository or standard | Relationship |
|---|---|
| [ver-cy/elmm](https://github.com/ver-cy/elmm) | The specification. This repository is the running instance of the ELMM profile: the schemas here are vendored from it, and its SHALL text is the behavior contract the resolver and CI implement. |
| [ver-cy/plmm](https://github.com/ver-cy/plmm) | The Product Landscape Meta-Model, the single governed Landscape (`deploy.portfolio` is an illustrative instance). It is registered here as `vercy.plmm`; it composes AISMM and references APMM, OUMM and CollMM. |
| [ver-cy/world-models](https://github.com/ver-cy/world-models) | The neutral catalogue of meta-model cards. Any of its models can register here as a Core model by adding one entry file and its edges; that path is the point of the zero-change registration guarantee. |
| [ver-cy/meta-universe](https://github.com/ver-cy/meta-universe) | The Meta-Universe standard, the substrate. Every mechanism this registry relies on is bound by reference to it (ARCH-002 versioning, ARCH-003 identity, ARCH-009 fingerprint, ARCH-014 policy, ARCH-016 composition, ARCH-017 traversal, ARCH-018 mastership, CORE-009 and CORE-012 projection, V0 to V5 gates, FED-013 discovery). The registry adds no parallel machinery; it profiles the upstream `entry.schema.json` and lets the MMDG edge record be the one genuinely new artifact. |

## Status and versioning

- **Current version:** v0.3.0, Working Draft. See [CHANGELOG.md](CHANGELOG.md). v0.3 adds the external-to-internal transform: the normative spec, the ver.cy policy profile, the instantiation manifest schema, the v0.3 additive extension of the node schema, the `instantiate.py` button, and the sixth CI check. v0.2 added the unified registry: the external standards discovery catalogue, the two orthogonal facet axes (cluster and industry), the facet vocabularies, the build and query tooling, and the unified index. The v0.1 resolver, MMDG, and admission gate are unchanged and still pass, as are the v0.2 facet layer and its check.
- Versioning follows ARCH-002. Major versions of any registered model are distinct registry identities that may coexist during migration.
- Contributions follow [CONTRIBUTING.md](CONTRIBUTING.md): one proposal per pull request, CI must pass, decisions the ELMM spec marks adopted are not reopened by pull request.
- License: Apache-2.0. See [LICENSE](LICENSE).
