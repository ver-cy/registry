# The external-to-internal transform

Workstream B6 of the ver.cy registry. The normative specification of the
transform that takes one external standard from the unified registry and
instantiates an internal tenant meta-model from it, overlaying the ver.cy
governance and recording full lineage back to the external source.

## 0. Status and conformance language

Document class: normative. Status: working draft, v0.1, aligned with registry
schema v0.3.

The keywords SHALL, SHALL NOT, SHOULD and MAY are used per common standards
practice. A tool, an emitted artifact or a run is conformant when it satisfies
every SHALL in this document. The invariants of section 9 are the conformance
core: an implementation that violates any B6 invariant is non-conformant
regardless of what else it does.

This document binds by reference. The Meta-Universe architecture (Extension-Model,
Policy-Consistency ARCH-014, Meta-Model-Composition ARCH-016, Data-Mastership
ARCH-018, Provenance-Graph, Meta-Model identity ARCH-002, ARCH-003, ARCH-009),
the Common Operating Law (the invariant controls IC-1 to IC-8 and the delegation
tiers T1 to T3), the AISMM external binding shape (aismm-external-binding.schema.json
in the reference runtime's software meta-model repository), and the registry
schemas (registry-node.schema.json, instantiation-manifest.schema.json,
external-standard.schema.json) are cited by id and never restated here.

## 1. What the transform is, and the one-click promise

The registry carries two entry classes. Internal meta-models are MMDG nodes:
few, governed, versioned, joined by typed edges, and walked by the resolver.
External standards are references: many (the catalogue holds over a thousand),
faceted, discoverable, and never walked. An external standard is a citation the
registry can find, not a node it can compose.

The external-to-internal transform is the single operation that crosses that
boundary. Its input is one row of external/external-standards.csv, a tenant, and
a policy profile. Its output is a new internal Model Registration Record, a
first-class MMDG node the resolver can compose, plus an instantiation manifest
that records exactly how the crossing was made. It is the flagship button, and
it SHALL be one command:

```
python tools/instantiate.py --external <registry_ref> --tenant <tenant> \
    --profile <profile> --at <iso8601>
```

The one-click promise is that this single operation does three things that the
architecture otherwise specifies separately, and does them together, from one
set of inputs, deterministically and reproducibly, validating both artifacts
before either is written:

1. it binds the external standard structurally (the Extension-Model term);
2. it overlays the ver.cy governance (the Policy-Consistency term); and
3. it declares who masters the data and records the lineage (the Data-Mastership
   term, with Provenance-Graph).

Nothing about the standard's own governance is transferred. The external standard
keeps its owner, its version cadence and its semantics. The transform registers a
tenant's decision to reference and govern that standard as an internal model; it
does not fork or absorb it.

## 2. The formula

The owner states the transform as a composition of three architecture documents,
made a single operation:

```
external-to-internal = Extension-Model + Policy-Consistency + Data-Mastership
```

Each term is an existing normative document, and the transform is their
composition:

- **Extension-Model** governs importing and extending an external standard as a
  versioned, self-describing Semantic Package, preferring extension over
  duplication and never redefining imported semantics. Composition is settled by
  Meta-Model-Composition (ARCH-016), which supplies the compositional roles R1 to
  R8 and the link mechanisms the binding uses. The transform emits an AISMM
  external_binding block as the concrete artifact of this term.
- **Policy-Consistency (ARCH-014)** keeps the overlaid normative rules
  satisfiable and rejects a contradiction before merge. The transform emits an
  applied_policies list drawn from the named policy profile, which carries the
  eight Common Operating Law invariant controls IC-1 to IC-8; ARCH-014 is the
  discipline that keeps that set coherent.
- **Data-Mastership (ARCH-018)** decides, for the mirrored dataset, who is the
  master. An imported external standard is a fixed special case of Pattern E
  (external-mastered): the standards body masters, the flow is inbound. The
  transform emits a Mastership Register stanza declaring exactly this, and a
  Provenance-Graph derivedFrom edge recording the lineage.

Made one operation means the three terms are computed from the same inputs in one
deterministic pass and validated together before either artifact is written, so
that an accepted pair is always coherent: binding without governance, or
governance without mastership, or mastership without lineage, is never an accepted
result. The two writes are sequential rather than a filesystem transaction; the
coupling is enforced at validation time, before the first write.

## 3. Inputs and outputs

### 3.1 Inputs

1. **An external standard row.** One row of external/external-standards.csv,
   selected by its Acronym or, when it has none, its Name (the registry_ref). The
   row carries the columns the transform reads: Name, Acronym,
   SpecificationSourceURL, NamespaceURI, Year, CompositionalRole (R1 to R8),
   DefaultLinkType, and Industry (the inherited sector facet). The row is the
   master reference; the transform never inlines the standard's content.
2. **A tenant.** The party instantiating the model. The tenant becomes the
   publisher, owner and steward of the internal record and the declarant of its
   mastership stanza (IC-1: mastership is declared by a named party, never
   inferred). The tenant SHALL be a simple lowercase token so it can be the first
   segment of the registry id.
3. **A policy profile.** A file under transform/policy-profiles/, default
   vercy-baseline. It carries default_delegation_tier and an ordered list of
   policy ids. The profile is the Policy-Consistency term made concrete: its
   policy ids are exactly the set the transform records in applied_policies.

### 3.2 Outputs

1. **An internal Model Registration Record.** A YAML entry written to
   entries/<internal_id>.yaml. It is a full MMDG node: it validates against
   registry-node.schema.json (v0.3) with every required field filled, and it
   carries the four v0.3 provenance fields tenant, derived_from, external_binding
   and applied_policies. Once written it is picked up by build_index like any
   other internal entry.
2. **An instantiation manifest.** A JSON file written to
   instantiations/<instantiation_id>.manifest.json. It records the full transform
   result: how the external model was bound, which policies were overlaid, who
   masters the data, the delegation tier, and the lineage. It validates against
   instantiation-manifest.schema.json.

## 4. The six steps

The transform is a pure function of its inputs. It runs the following six steps
in order, deterministically (no wall clock, no randomness; the only time value is
the --at argument).

### Step 1: select the external standard

Read external/external-standards.csv and select the one row whose Acronym equals
the registry_ref, or whose Name equals it when no Acronym matches. If no row
matches, the transform SHALL fail closed with a diagnostic naming the
registry_ref; a fresh instantiation SHALL NOT be produced for a standard that is
not catalogued (the internal model must be mirrored-external of a real source,
IC-3). The selected row is the transform's external input for every later step.

### Step 2: derive the binding

From the row's CompositionalRole and DefaultLinkType, derive the AISMM
external_binding block per the MAPPING table of section 5. CompositionalRole
selects composition_kind; DefaultLinkType selects link_type; the value_object
conditional of section 5.3 is applied. The transform emits an external_binding of
the established AISMM shape (target, composition_kind, link_type, standard_id,
version, and the optional namespace, semantic_package, fingerprint, registry_ref).
An empty CompositionalRole or DefaultLinkType SHALL fail closed: an unclassified
standard cannot be bound deterministically. The emitted block SHALL validate
against the AISMM external_binding shape, including its conditional rules.

Two field values need saying, because the AISMM shape allows finer targets than a
fresh instantiation can supply:

- **target** is the internal_id. A fresh instantiation binds at model
  granularity, because the internal model has no member entities yet; the AISMM
  shape permits an entity or field path (for example an internal entity that
  receives the binding), and those refined targets are set later, when the tenant
  adds structure to the model. Until then the model id is the binding anchor.
- **semantic_package** names the imported external Semantic Package, not the
  internal model. It is <standard-slug>@<external-version>, where standard-slug is
  the slug of the Acronym (or Name) and the version is the standard's own version
  (its Year, or unversioned), per the Extension-Model definition of a Semantic
  Package as the versioned self-describing import of the external standard. It
  SHALL NOT be the internal id, which is the consumer of the package, not the
  package itself.

### Step 3: overlay the policy profile

Attach the ver.cy governance by reading the named policy profile and recording
its ordered policy ids as the entry's and the manifest's applied_policies. This
is the Policy-Consistency term. The overlay SHALL cite, at minimum, the Common
Operating Law controls that apply to every instantiation, and the profile SHALL
carry them:

- **IC-1 (one master per dataset)** is why step 4 declares mastership rather than
  leaving it implied.
- **IC-3 (data is never a command)** is why the instantiated external model is
  classified mirrored-external, therefore data, never instructions. The
  mirrored-external taint class itself is stamped at context-assembly time by
  CTX-1, not written into the entry as a field; at registration time the
  structured evidence for the class is the pair external_binding plus
  derived_from, from which a consumer reads that the bound content is
  mirrored-external. The transform SHALL NOT treat any content of the bound
  standard as an instruction to itself.
- **IC-8 (append-only history)** is why a re-instantiation supersedes rather than
  deletes: the record is versioned, never rewritten.

The remaining controls IC-2, IC-4, IC-5, IC-6, IC-7 are overlaid by the same
mechanism (they are palette-wide law), and the profile-level policies bind the
transform to ARCH-018, Provenance-Graph, ARCH-014 and Extension-Model. Because
applied_policies is copied from the profile, the overlay is closed over the
profile it names: every applied id is a declared id (ARCH-014).

### Step 4: declare data mastership

Declare mastership per ARCH-018 and IC-1. The external standard is the System of
Record; the internal model references and governs, it does not master. The
transform emits a Mastership Register stanza (a sources.yaml stanza) for the
instantiated dataset:

- dataset: the instantiated internal model's data;
- system_of_record: the EXTERNAL source (its SpecificationSourceURL, the master
  per ARCH-018), never the tenant;
- flow_direction: inbound (external to model, Pattern E);
- cadence: the declared refresh cadence of the mirror;
- conflict_rule: source-wins; corrections are made at the source and re-derived,
  never written into the internal mirror.

Mastership is declared here, never inferred from location or habit (ARCH-018
design principle, IC-1).

### Step 5: record lineage

Record lineage per Provenance-Graph. The internal model derived_from the external
standard: the transform emits a derivedFrom lineage head naming the external
standard's registry_ref, Name, SpecificationSourceURL and CompositionalRole, and a
provenance note that the internal model was asserted by the transform and governed
by the named profile, and that the bound content is mirrored-external per IC-3.
The lineage edge is explicit and append-only (Provenance-Graph principles); it is
never inferred after the fact and never broken.

### Step 6: emit the entry and the manifest, and register the entry as an MMDG node

Assemble and write the two artifacts:

- the internal entry to entries/<internal_id>.yaml, with the fixed field values of
  section 6, the inherited industry facet, and the four v0.3 provenance fields;
- the manifest to instantiations/<instantiation_id>.manifest.json, with the full
  transform result of section 7.

The written entry is thereby registered as an MMDG node: build_index picks it up
from entries/, the resolver can compose it, and CI validates it against the node
schema alongside the four seed entries. The instantiation_id and the
semantic_fingerprint are deterministic hashes over canonical content (section 8),
so the pair is byte-reproducible.

## 5. The MAPPING

The binding is derived mechanically from the external standard's registry
classification. The two maps are normative in this specification and in the tool.

### 5.1 DefaultLinkType to external_binding.link_type

| DefaultLinkType | link_type  |
|-----------------|------------|
| EMBED           | embed      |
| REFERENCE       | reference  |
| MIX-IN          | mixin      |
| ALIGN           | align      |
| EXTEND          | extend     |
| COMPOSE         | reference  |
| N/A             | annotate   |

COMPOSE maps to reference (an aggregate is drawn in by reference, not embedded);
N/A maps to annotate (an infrastructure standard is recorded as an annotation, not
composed).

### 5.2 CompositionalRole to external_binding.composition_kind

| CompositionalRole | composition_kind |
|-------------------|------------------|
| R1                | value_object     |
| R2                | code             |
| R3                | code             |
| R4                | entity           |
| R5                | facet            |
| R6                | entity           |
| R7                | entity           |
| R8                | attribute        |

### 5.3 The value_object override

When composition_kind resolves to value_object (from R1), link_type SHALL be
forced to embed, whatever the DefaultLinkType column said. This is the AISMM
conditional rule (a value object is carried inline). The transform applies it
after the two maps.

### 5.4 Facet inheritance

The instantiated internal entry inherits the external standard's Industry facet
verbatim: the entry's industry array equals the row's Industry codes, in order,
unchanged. Cluster is left unset unless the standard's Group has an obvious
cluster; the transform SHALL NOT guess a cluster.

## 6. The internal entry: fixed field derivation

The transform fills every required registry-node field deterministically from the
external row and the profile. The fixed choices are:

- id: <tenant>.<standard-slug>, publisher-prefixed and dot-separated per the id
  pattern; the standard-slug is the slug of the Acronym, or of the Name when there
  is no Acronym;
- kind: domain (the projection of role core);
- role: core;
- origin: internal (the model is authored inside the registry governance domain,
  even though it derives from an external source);
- status: draft;
- version: 0.1.0;
- access: public;
- license: inherited from the standard where the catalogue carries one, otherwise
  Apache-2.0;
- source.repository: the external SpecificationSourceURL (the master, ARCH-018);
- publisher, owner, steward: the tenant;
- industry: the external row's Industry, verbatim (section 5.4);
- derived_from, external_binding, applied_policies, tenant: the four v0.3
  provenance fields, filled from steps 2 to 5.

The entry's csn, primary_namespace and display_alias are derived from the tenant
and the standard-slug so the record has a stable Canonical Semantic Name and
namespace (ARCH-003). A fresh instantiation carries an empty requires list and no
edges: it references the external standard, not another internal node, so the
graph is unchanged by the registration (the zero-change guarantee holds).

## 7. The instantiation manifest

The manifest records the full transform result, one JSON file per instantiation:

- instantiation_id: a deterministic hash over the canonical inputs (tenant,
  registry_ref, profile, and the --at timestamp), so each instantiation event has
  a distinct id and a distinct manifest file, and a re-instantiation supersedes
  rather than overwrites (IC-8, B6-I11);
- created_at: the --at timestamp, never the wall clock;
- tenant: the instantiating party;
- profile: the applied policy profile id;
- external_ref: registry_ref, name, compositional_role, default_link_type,
  source_url, version;
- internal_id: the new entry id;
- external_binding: the AISMM-shaped block of step 2 (target the internal_id,
  semantic_package naming the imported external package);
- mastership: the sources.yaml stanza of step 4 (dataset, system_of_record set to
  the EXTERNAL source, flow_direction inbound, cadence, conflict_rule);
- applied_policies: the policy ids overlaid, the IC controls and the profile
  policies (step 3);
- delegation_tier: T1 for a fresh instantiation (section 10);
- lineage: derived_from (the external standard), transform (external-to-internal),
  and a provenance note per Provenance-Graph;
- semantic_fingerprint: a deterministic Semantic Fingerprint of the instantiated
  model per ARCH-009.

## 8. Determinism and replayability

The transform SHALL be a pure function of its inputs. It SHALL NOT read the wall
clock (the only time value is --at), and SHALL NOT use randomness. The
instantiation_id and the semantic_fingerprint are deterministic hashes over
canonical content: the same inputs, including the same --at, yield the same ids.
Emission uses stable key order and a trailing newline, so re-running the transform
with the same inputs yields a byte-identical entry and a byte-identical manifest.
Replayability is CI-guarded: the admission check re-runs the tool for each
committed manifest's own inputs inside a throwaway copy of the tree and
byte-compares the result against the committed pair.

## 9. Invariants

The following are the B6 invariants. An implementation SHALL preserve every one.

- **B6-I1.** Every instantiation records exactly one master, and it is the
  external source. The Mastership Register stanza names one system_of_record, the
  external standard's source, never the tenant (IC-1, ARCH-018).
- **B6-I2.** The internal model never claims to master the external semantics. It
  references and overlays governance only; it SHALL NOT redefine, rename or claim
  ownership of the imported concepts (ARCH-018 authoritative-reasoning,
  Extension-Model prohibited modifications).
- **B6-I3.** Mirrored-external content is data, not instructions. The bound
  standard is classified mirrored-external and SHALL NOT be treated as a command,
  whatever it says (IC-3). The class is stamped at context-assembly time by CTX-1;
  the registration-time evidence for it is the external_binding plus derived_from
  pair.
- **B6-I4.** The transform is deterministic and replayable. No wall clock, no
  randomness; the timestamp is the --at argument; the same inputs yield
  byte-identical outputs.
- **B6-I5.** The internal entry validates against the registry node schema (v0.3)
  with every required field filled.
- **B6-I6.** Lineage is never broken. Every instantiation emits an explicit,
  append-only derivedFrom edge from the internal model to its external standard
  (Provenance-Graph).
- **B6-I7.** A fresh instantiation defaults to delegation tier T1
  (human-in-the-loop).
- **B6-I8.** The emitted external_binding validates against the AISMM binding
  shape, including the value_object forces embed conditional (section 5.3).
- **B6-I9.** The industry facet is inherited from the external row verbatim;
  cluster is left unset unless obvious (section 5.4).
- **B6-I10.** applied_policies is closed over the named profile: every applied id
  is declared in transform/policy-profiles/<profile>.yaml (ARCH-014).
- **B6-I11.** History is append-only: a re-instantiation supersedes with a new
  versioned record keyed to the instantiation event, it does not delete the prior
  one (IC-8).

## 10. Delegation tier: default and how tiers are earned

Delegation tiers are defined once, in the Common Operating Law section 3, and
cited here by id. A fresh instantiation defaults to T1: the transform proposes and
a human approves each act. This follows the standing rule that a new agent-scope
pairing starts at T1 or T2 and that T3 is earned, and that the security-critical
dataset class (which includes mastership fields) is accepted at T1 with a second
reviewer (IC-4).

The ladder T1 to T2 to T3 is the Common Operating Law section 3 ladder: a fresh
instantiation starts at T1 (human-in-the-loop), a lower-risk scope may be granted
at T2 (human-on-the-loop), and T3 (autonomous-with-audit) is never a starting
tier, it is earned.

Tier changes are Owner or Steward decisions recorded in the delegation contract
register (Common Operating Law section 3); the transform declares only the
starting tier and never raises it.

## 11. Conformance

A conformant transform:

- emits an entry that is schema-valid against registry-node.schema.json (v0.3),
  with the four v0.3 provenance fields present and non-empty;
- emits a manifest that is schema-valid against
  instantiation-manifest.schema.json;
- is byte-reproducible: re-running with the same inputs, including the same --at,
  produces byte-identical artifacts; and
- preserves every B6 invariant of section 9.

An emitted pair that fails any of the four is non-conformant. The admission check
ci/check_instantiations.py verifies all four mechanically for every committed
instantiation, and passes vacuously while the transform is unused, so the button
can be shipped incrementally without breaking the gate.

## 12. Worked example

The reference worked example instantiates HL7 FHIR for a tenant named acme, at a
fixed timestamp.

Inputs:

- external: FHIR (the row whose Acronym is FHIR in
  external/external-standards.csv: Name HL7 FHIR, Group Healthcare and Life
  Sciences, SpecificationSourceURL https://hl7.org/fhir/, NamespaceURI
  http://hl7.org/fhir, CompositionalRole R4, DefaultLinkType REFERENCE, Industry
  healthcare-life-sciences);
- tenant: acme;
- profile: vercy-baseline (the default);
- at: 2026-08-10T00:00:00Z (a fixed timestamp).

Command:

```
python tools/instantiate.py --external FHIR --tenant acme \
    --profile vercy-baseline --at 2026-08-10T00:00:00Z
```

Expected derivations, per the MAPPING and the fixed field rules:

- composition_kind: entity (R4); link_type: reference (REFERENCE); no value_object
  override applies;
- internal_id: acme.fhir; role core, kind domain, status draft, version 0.1.0,
  access public, origin internal;
- external_binding.target: acme.fhir (model granularity, section 5);
  external_binding.semantic_package: fhir@<external-version> (the imported
  external package, section 5);
- source.repository: https://hl7.org/fhir/ (the master, ARCH-018);
- steward, publisher, owner: acme;
- industry: healthcare-life-sciences (inherited verbatim);
- mastership.system_of_record: the external FHIR source, not acme; flow inbound;
- applied_policies: the vercy-baseline policy ids (IC-1 to IC-8 plus
  mastership-external, lineage-required, policy-consistency, extension-binding);
- delegation_tier: T1.

The worked-example entry (entries/acme.fhir.yaml) and manifest
(instantiations/<id>.manifest.json) are not hand-written. They are generated by
running the tool above and committed as fixtures by the operator after the
workflow, so the example is reproducible byte for byte, and the admission check
replays it to prove so.

Committing an instantiation is a four-artifact operation, not two. After running
the tool, the operator regenerates the unified index (python tools/build_index.py)
and the resolver fixtures under examples/expected/ (via resolver/resolve.py),
because the new node enters the unified index and shifts the resolver's
registry-wide coverage line. The operator then commits all four artifacts
together: the new entries/<id>.yaml, the new
instantiations/<id>.manifest.json, the refreshed index/unified-index.json, and the
regenerated examples/expected/ fixtures. check_facets and check_resolve fail if
the generated artifacts are left stale, so shipping only the entry and the
manifest turns the gate red.
