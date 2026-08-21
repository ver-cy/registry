# Vercy V02: product direction and implementation record

Status: **accepted current direction**
Decision date: 2026-08-21
Applies to: the Vercy website, registry contracts, generated templates, and future meta-model specifications

## 1. Product thesis

Vercy is a public registry of versioned meta-model specifications: a catalogue of logical data structures without a mandatory storage format or access interface. Its purpose is to give AI agents connected, bounded and governed context that can act as a cache, an operational knowledge layer, or a master source for task-critical data.

A specification defines meaning, identity, hierarchy, ownership, questions, artifacts and operating rules. Formats, carriers and interfaces are selectable projections of that specification, not the specification itself.

```text
logical meta-model
  -> representation: Markdown | HTML | JSON | YAML | Mongo documents
  -> carrier: Git repository | file tree | Mongo database
  -> interface: Git | filesystem | HTTP | MCP files | Mongo API | MCP Mongo
  -> deployment profile: a validated combination of the above
```

Legacy AISMM, PLMM and other Vercy repositories remain reference assemblies. They demonstrate earlier complete builds and provide migration evidence; they are not the canonical contract for V02.

## 2. Canonical logical structure

Every catalogue entry describes:

- identity: name, stable id, namespace, family, category, industry, domain, aliases, tags and lifecycle;
- version: immutable version URL, previous versions, semantic diff and migration information;
- Bundle: a named grouping of Layers, or a reference to a child meta-model or master system;
- Layer: a named grouping of Findings, or a reference to a child meta-model or master system;
- Finding: a named and described unit of knowledge, with child-model/master bindings when applicable;
- Question: what the Finding must enable a reader or agent to answer, including answer shape and coverage state;
- Artifact: the evidence or data product that answers Questions, including serial-artifact rules;
- service package: Dimension, canon, patches, referenced schemas and standards, artifact rules, policies, CRUD processes, roles, access controls and exceptions;
- operational package: validation, provenance, freshness, synchronization, observability, security, privacy, retention, recovery and localization.

Stable identities must survive projection into every supported format and interface.

## 3. Dimension Owner Package

Every Dimension begins with a deployable owner package that creates the local world in which meta-models operate. At minimum it contains:

- Dimension identity, purpose, namespace and link to the Vercy meta-universe;
- owner, accountable roles and contacts;
- registries of meta-models, meta-objects, events and referenced systems;
- access, privacy, retention and change policies;
- selected storage and interface profiles;
- a root `AGENTS.md` and an instruction that helps the owner's AI agent discover, propose and populate suitable meta-models.

The agent recommends the smallest useful set of models, defaults private data to private storage, and writes only after owner approval.

## 4. Agent-first bootstrap invariant

Every generated meta-model package MUST begin with `AGENTS.md`. It is the cold-start document and declares, at minimum:

- model name and type;
- immutable Vercy specification URL;
- storage profile;
- interface and read path;
- process/policy reference.

The invariant also applies to database deployments. A Mongo projection therefore includes an equivalent bootstrap document, marked `readFirst: true`, plus a retrievable root `AGENTS.md` in the exported package. An agent must be able to orient itself without prior knowledge of the carrier.

## 5. Catalogue and machine contracts

The website is the human catalogue and discovery surface. Users can search by family, category, industry, domain, name and tags. Every model has its own site card/page containing its hierarchy, service package, versions and generator.

Every released version exposes an immutable AI instruction/specification as YAML at a stable URL. Meta-models may pin and reference that URL. Canonical machine contracts remain English to keep identifiers and automation stable; human pages and shared UI are localized.

## 6. Template constructor

Each model card contains a constructor that packages the same logical model for a selected representation, carrier and interface. Supported initial profiles are:

- Git or folders using Markdown, HTML, JSON or YAML;
- MCP backed by files;
- native Mongo database;
- MCP backed by Mongo.

Generated packages include `AGENTS.md`, the pinned specification reference, read/write processes, validation material and profile-specific bootstrap files. Projections must be lossless with respect to the logical contract.

## 7. Artifact identity and time

Artifact identity is not a date.

1. Prefer the unique id supplied by the declared master system.
2. Otherwise generate UUIDv7 or ULID.
3. Record time separately as RFC 3339 with seconds and an explicit timezone, for example `2026-08-20T14:32:07Z` or `2026-08-20T17:32:07+03:00`.
4. Never use a timestamp alone as the artifact identity.

Default filename: `<kind>--<artifact-id>--<slug>.<ext>`. A time-based fallback must include UTC seconds and entropy: `<kind>--YYYYMMDDTHHMMSSZ--<entropy>--<slug>.<ext>`.

## 8. Extension and patching

Extensions are explicit, versioned overlays. They may add Bundles, Layers, Findings, Questions, Artifacts or policy bindings, but may not silently replace stable identities or weaken inherited governance. Each patch declares its base version, operations, namespace, ownership, conflicts and validation result. Consumers can resolve the effective model and reproduce it deterministically.

## 9. Website information architecture

The primary navigation is intentionally limited to five product groups plus the main action:

1. Catalogue
2. Build
3. Learn
4. Standard
5. About
6. Create your world

The language selector remains at the right side of navigation and preserves the current page. Header, footer, content containers and primary blocks use one shared shell.

## 10. Implemented as of 2026-08-21

- Published the searchable catalogue at `/models/` with 114 model cards and individual model pages.
- Published the AISMM page and complete YAML projection with 13 named Bundles, 86 Layers, 380 Findings and 1,537 Questions, derived from the software-meta-model reference repository.
- Embedded the template constructor in model pages for Git/files/Mongo, Markdown/HTML/JSON/YAML, and Git/filesystem/MCP/Mongo interfaces.
- Made root `AGENTS.md` mandatory in generated packages, including a Mongo `readFirst` bootstrap document.
- Published the five-step Dimension starter at `/start/`, producing an 11-file owner package and an AI-agent instruction.
- Adopted master-system id, UUIDv7 or ULID for artifact identity and RFC 3339 timestamps with seconds and timezone as separate metadata.
- Consolidated site navigation and shared page shell; repaired the home-page footer and restored the established Vercy orbit logo.
- Restored EN/RU/ES/EL/ZH language switching with page preservation, browser-language detection and persisted preference.
- Kept legacy model repositories unchanged as examples of previous assembled versions.

## 11. Known follow-up work

- Complete editorial translation of all long-form historical page content; shared UI and catalogue controls are localized, but not every legacy paragraph has a human translation yet.
- Migrate additional legacy models to complete V02 native specifications, while retaining their earlier repositories as examples.
- Formalize immutable version URL routing, signature/checksum publication and automated semantic diffs for every release.
- Add conformance tests for round-trip equivalence across every advertised deployment profile.
- Persist catalogue data in the long-term registry backend without making that backend part of the logical standard.

## 12. Authority and related contracts

This document is the product direction and implementation record. Normative schema detail lives in [`../VERCY-REGISTRY-VNEXT.md`](../VERCY-REGISTRY-VNEXT.md); release acceptance lives in [`../CATALOGUE-CONTRACT-CHECKLIST.md`](../CATALOGUE-CONTRACT-CHECKLIST.md). If older roadmap prose conflicts with this decision, this document takes precedence until superseded by a dated accepted decision.
