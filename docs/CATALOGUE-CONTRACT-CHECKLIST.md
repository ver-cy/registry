# Catalogue contract checklist

This checklist is the acceptance gate for every complete meta-model specification.

## Discovery

- [ ] Family, category, industry, domain, name/aliases and tags are present.
- [ ] Stable id, namespace, version, immutable URL and prior-version links resolve.
- [ ] Owner, steward, publisher, license, lifecycle and provenance are declared.

## Logical model

- [ ] Every Bundle, Layer, Finding, Question and Artifact has a stable local id.
- [ ] Responsibilities and boundaries do not overlap silently.
- [ ] Child-model references resolve and preserve ownership.
- [ ] Every governed dataset has one master at its declared grain.
- [ ] Required Questions have an answer shape and coverage state.
- [ ] Serial Artifacts have deterministic naming, ordering and retention rules.

## Operations and governance

- [ ] Read/Add/Edit/Delete/Retire instructions exist.
- [ ] Owner, steward, author, reviewer and auditor responsibilities exist.
- [ ] Access is defined at all relevant grains with explicit exceptions.
- [ ] Policies and process profile are version-pinned.
- [ ] Change, semantic diff, migration and rollback behavior are defined.

## Trust and operation

- [ ] Provenance, evidence and fingerprints are reproducible.
- [ ] Validation suite and examples exist.
- [ ] Freshness, synchronization and observability obligations exist.
- [ ] Security, privacy, purpose, retention and recovery rules exist.
- [ ] `AGENTS.md` and the immutable AI YAML URL cold-start successfully.

## Portability

- [ ] The logical specification names no mandatory storage format or interface.
- [ ] Every supported representation declares a lossless mapping back to the logical form.
- [ ] Every deployment profile declares carrier, interfaces and operational semantics.
- [ ] At least one generated template passes its profile validation.

