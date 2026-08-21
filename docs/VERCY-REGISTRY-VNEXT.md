# Vercy Registry vNext

Status: accepted architecture; implementation in progress
Scope: Vercy as a registry and generator of format-independent meta-model specifications

Product direction and implementation record: [`roadmap/VERCY-V02-DIRECTION.md`](roadmap/VERCY-V02-DIRECTION.md).

## 1. Product definition

Vercy is the public catalogue of versioned meta-model specifications that give an AI a connected, bounded and governed context for a task. A registered specification describes the logical structure and operating semantics of a meta-model. It does not require a particular file format, database, transport or query protocol.

Storage and access are orthogonal adapters:

```text
logical specification
  -> representation descriptor (YAML, JSON, Markdown, HTML, Mongo documents)
  -> carrier descriptor (Git tree, file tree, Mongo database)
  -> interface descriptor (filesystem, Git, HTTP, MCP, Mongo API)
  -> deployment profile (one tested combination)
```

The same logical specification MUST preserve identity, hierarchy, questions, artifacts, references, policies and access semantics when projected through any conforming adapter.

## 2. Evidence from the current Vercy family

The redesign reuses existing work rather than inventing a parallel standard.

| Existing source | Keep | Gap closed by vNext |
|---|---|---|
| Meta-Universe ARCH-019 Data Portability and Access | separation of logical structure, representation, carrier, access and traversal | expose the separation as catalogue descriptors and selectable templates |
| Meta-Universe ARCH-002/003/009 | versioned identity, namespaces and semantic fingerprints | make version history and stable URLs first-class catalogue fields |
| Meta-Universe ARCH-014/016/018 | policy consistency, composition and one master per dataset | attach these rules at bundle, layer, finding and artifact grain |
| Meta-Universe Extension-Model | additive extension by reference | define a machine-executable patch package with admission rules |
| AISMM bundles b0-b12 | broad coverage of product, architecture, implementation, behavior, UX, operations, quality, change, knowledge, data/AI, organization and economics | normalize their authoring shape into Bundle/Layer/Finding/Question/Artifact |
| AISMM b9 traceability and source bindings | provenance, RAG, coverage, relationships and extraction recipes | make provenance and derived indexes mandatory service concerns |
| PLMM | landscape composition, products, relationships, capabilities, processes, operations, governance, change, consistency, routing and portfolio | turn landscape composition and governance into catalogue-visible structures |
| ELMM/MMDG | registry identity, exports/requires, typed relationships, bounded resolver | demote ELMM from product identity to reusable graph/resolution contracts |
| Vercy registry | 11 internal nodes, 1180 external standards, industry/cluster facets, deterministic CLI search | add complete specifications, versions, tags, web search and cards |
| Vercy processes | 81 processes in seven families, including genesis, access, contribution, actuation, federation and quality | bind a selected process profile to every specification and expose CRUD instructions |
| world-models | 112 neutral model cards grouped into 15 clusters | migrate cards into the versioned catalogue contract |

## 3. Catalogue search and discovery

Every published version is indexed independently and the latest compatible version is marked.

Required filters:

- family: related specifications maintained as a family;
- category: architectural role or catalogue class;
- industry: sector vocabulary, multi-valued;
- domain: subject area, multi-valued;
- name and aliases;
- tags;
- publisher, owner, lifecycle status, license and conformance level;
- supported formats, carriers, interfaces and deployment profiles;
- exported concepts and dependencies.

Search results MUST distinguish a complete meta-model specification from an external reference standard and from a generated deployment template.

## 4. Specification card

### 4.1 Identity and lifecycle

- stable catalogue id, Canonical Semantic Name and primary namespace;
- name, aliases, summary, family, category, industries, domains and tags;
- semantic version, immutable version URL, latest-version URL and links to every prior/successor version;
- lifecycle state, compatibility declaration, migration guides and deprecation/retirement policy;
- publisher, sovereign owner, stewards, license, provenance and semantic fingerprint;
- Dimension membership and authoritative specification repository, when one exists.

### 4.2 Logical structure

The normative tree is:

```text
MetaModel
  Bundle[]
    Layer[] | child_model_ref[] | master_binding[]
      Finding[] | child_model_ref[] | master_binding[]
        Question[]
        Artifact[]
```

- A Bundle groups Layers and MAY compose a child meta-model by reference.
- A Layer groups Findings and MAY compose a child meta-model by reference.
- A Finding is a named, bounded unit of knowledge that answers Questions. It is not tied to a document or database object.
- A Question defines the expected semantic answer shape and whether an answer is required.
- An Artifact is a material answer, evidence object or generated output. It MAY be singular or serial.
- A master binding may occur at Bundle, Layer, Finding or Artifact grain, but each governed dataset has exactly one authoritative master at that grain.

Every node has a stable local id, title, description/responsibility, boundary, references and optional policy/access overrides. Child references never copy ownership.

### 4.3 Artifact and serial-information contract

Each artifact declaration includes:

- artifact kind and semantic media class;
- schema or expected answer shape;
- singular or serial cardinality;
- naming prefix/suffix and deterministic path/key rules for serial items;
- ordering, partitioning and pagination rules;
- retention, archival and tombstone behavior;
- provenance/evidence requirements;
- sensitivity and access class;
- validation rules and examples;
- permitted representation descriptors, without selecting one as canonical storage.

### 4.4 Service package

The service package travels with the logical structure:

1. Dimension, namespace authority and internal specification links.
2. Canon, base version, applied patches, referenced schemas and external standards.
3. Artifact requirements and serial naming rules.
4. Policies and adopted process profile.
5. Read/Add/Edit/Delete/Retire operating instructions, including validation and rollback.
6. Ownership, stewardship, authoring, review and audit roles.
7. Access rules at model, Bundle, Layer, Finding and Artifact grain, plus explicit exceptions.
8. Imports, exports, dependencies, compatibility and composition relationships.
9. Validation suites, conformance claims, examples and coverage declarations.
10. Provenance, change log, decisions, event log and semantic-diff rules.
11. Freshness, synchronization, observability, backup/recovery and incident obligations.
12. Security, privacy, purpose limitation, retention and credential-reference rules.
13. Localization labels and documentation languages where public discovery requires them.

Items 8-13 are the material omissions in the initial request found by comparing the existing specifications and process palette.

## 5. Agent bootstrap

Every deployed meta-model MUST expose `AGENTS.md` at its logical root, even if its data is held in MongoDB. The file is a bootstrap locator, not the whole model.

Minimum content:

```yaml
name: Example model
catalogue_id: example.model
type: AISMM
specification: https://ver.cy/catalog/example.model/1.2.0/ai.yaml
storage_profile: https://ver.cy/profiles/mongo-mcp/1.0.0.yaml
interface: https://ver.cy/interfaces/mcp/1.0.0.yaml
processes: https://ver.cy/process-profiles/managed/1.0.0.yaml
```

`AGENTS.md` MUST remain human-readable, contain no credentials, and give a cold agent enough information to fetch the version-pinned AI instruction and determine how to traverse the deployment. A database deployment stores this file beside the connection bootstrap or serves it from a fixed discovery endpoint.

## 6. Versioned AI instruction

Every catalogue version exposes an immutable YAML instruction:

```text
https://ver.cy/catalog/{catalogue-id}/{semver}/ai.yaml
```

It contains identity, the complete logical tree, traversal order, references, mastership, access, process bindings, validation commands and adapter links. `latest/ai.yaml` MAY redirect or resolve to a version but cross-model references MUST pin a major or exact version according to their compatibility policy.

The YAML is a projection of the catalogue record, not a second manually maintained source. CI regenerates it deterministically and rejects drift.

## 7. Format, carrier and interface descriptors

### 7.1 Representation descriptor

Describes how every logical node and field maps to YAML, JSON, Markdown, HTML or Mongo documents; canonicalization back to the common logical form; supported artifact classes; losslessness; validation and examples.

### 7.2 Carrier descriptor

Describes containment and location: Git repository, directory tree or Mongo database. It defines roots, path/key conventions, version pinning, atomicity, history and backup behavior.

### 7.3 Interface descriptor

Describes operations independently of representation and carrier: filesystem, Git, HTTP, MCP or Mongo API. It declares discovery, read, query, pagination, add, edit, delete/retire, transaction semantics, authentication references, error model and capability negotiation.

### 7.4 Deployment profile

A tested composition of one representation, one carrier and one or more interfaces. Initial profiles:

- Git + Markdown files;
- Git + HTML files;
- Git + JSON files;
- Git + YAML files;
- MCP + files;
- MCP + database;
- MongoDB + Mongo API;
- MongoDB + MCP.

The online generator takes a specification version and a profile, then returns a ready-to-fill package with `AGENTS.md`, manifests, folders/collections, validators and example records.

## 8. Patch and extension model

A patch is an immutable, versioned Extension Package. It declares:

- target catalogue id and compatible base-version range;
- patch namespace and owner;
- ordered operations (`add`, `refine`, `deprecate`, `retire`, `bind-master`, `bind-policy`);
- target stable ids, preconditions and expected fingerprints;
- new Bundles/Layers/Findings/Questions/Artifacts in the patch namespace;
- conflicts, migration notes, validation suite and resulting fingerprint.

Rules:

1. A patch MUST NOT silently mutate stable identity or weaken a base invariant.
2. Additions use the patch owner's namespace and remain attributable to it.
3. `refine` may narrow or strengthen; incompatible replacement requires a new major version or fork.
4. Removal is `deprecate` then `retire`; published ids remain resolvable as tombstones.
5. The same patch set in the same order over the same pinned base produces the same result.
6. Conflicting writes fail closed and require an explicit resolution package.
7. Generated views retain the base and patch provenance chain.

## 9. Dimension Owner Package

Every Dimension MUST deploy one base owner package before registering domain models. It is the constitutional manifest and namespace authority for that Dimension.

Required contents:

- Dimension id, name, version, owner and accountable roles;
- link to the governing Meta-Universe/Vercy version;
- namespace root, allocation policy and reserved namespaces;
- registry endpoints for meta-models, meta-objects, events, contracts, projections, agents/participants and artifacts;
- identity/fingerprint and signing-key references;
- governance, change, access, delegation, retention and incident policies;
- discovery document and supported federation capabilities;
- mastership register for the registries themselves;
- event/change log and conformance statement;
- bootstrap `AGENTS.md` and versioned AI instruction;
- succession/recovery declaration so the Dimension does not die with one operator.

The package declares authority; it does not own the content registered by sovereign model owners.

## 10. Delivery slices

1. Catalogue contracts and examples: specification, patch, Dimension package, descriptors and deployment profile.
2. Deterministic validation and AI-YAML projection.
3. Migration of current registry nodes and selected AISMM/PLMM/world-model cards.
4. Static catalogue build with full-text/faceted search and versioned cards.
5. Template generator and the eight initial deployment profiles.
6. MCP read/query surface, then governed write operations.
7. Production publication on `ver.cy`, compatibility redirects and migration documentation.

The catalogue contracts are the source of truth. The website, AI instructions, indexes and templates are generated projections.
