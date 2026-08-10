# Registry tooling

Four deterministic scripts build, query and extend the unified registry. The
three build and query steps are stdlib plus PyYAML; `instantiate.py` (the B6
button) additionally needs jsonschema, because it validates both artifacts it
emits before writing them. Every script locates the registry root from its own
file location (the parent of `tools/`, matching the `ci/_common.py` convention),
so it runs from any working directory and on a copied tree. Every script exits
non-zero with a diagnostic on `stderr` when an input is missing, a facet code is
unknown, or a generated artifact is invalid.

The two entry classes sit on two orthogonal facet axes. Cluster says what a
thing is (the fifteen ontological clusters); industry says which sector uses or
governs it (the `vercy-industry` vocabulary). Internal meta-models carry both
axes in their entry files. External standards inherit industry from their Group
through `facets/group-industry-map.csv`; cluster for external standards is
optional in v0.2 and currently empty.

## Pipeline

    facets/group-industry-map.csv  \
    facets/industry.yaml            >-- import_external.py --> external/external-standards.csv
    external/external-models.source.csv /

    entries/*.yaml                 \
    external/external-standards.csv >-- build_index.py --> index/unified-index.json
    facets/*.yaml                  /

    index/unified-index.json ------- query.py (read-only CLI)

### 1. import_external.py

    python tools/import_external.py [--root <registry-root>]

Reads the source catalogue and the Group to industry map, and writes
`external/external-standards.csv`: every source row, all source columns and
values preserved verbatim, with two columns appended. `Origin` is always
`external`. `Industry` is the semicolon-joined industry codes for that row's
Group, taken from the map in the map's order.

Column order is the source columns in their original order, then `Origin`, then
`Industry`. Rows are sorted by `(Group, Acronym, Name)`. The writer uses an LF
line terminator and minimal quoting. The run is idempotent: it reads the source,
never its own output, so re-running yields a byte-identical file.

It exits non-zero if any Group is absent from the map, or if any mapped code is
not a known industry code in `facets/industry.yaml`. The diagnostic lists the
offending Groups or codes.

### 2. build_index.py

    python tools/build_index.py [--root <registry-root>]

Reads the internal entries (`entries/*.yaml`), the generated external CSV, and
the facet vocabularies, and writes `index/unified-index.json`: a deterministic
object with

  - `generated_from`: a fixed provenance note, no timestamp.
  - `totals`: `{internal, external, total}` counts.
  - `facets`: the five histograms `by_industry`, `by_cluster`, `by_role`,
    `by_origin`, `by_link_type`, each a sorted `code -> count` map.
  - `entries`: a sorted list of minimal records
    `{ref, origin, name, industry[], cluster[], role?, link_type?, group?}`.
    `ref` is the registry id for an internal entry, and the slug of the Acronym
    (falling back to the Name) for an external standard, made unique by a
    deterministic numeric suffix on collision. `role`, `link_type` and `group`
    are present only for external standards.

The JSON is emitted with sorted keys, two space indent and a trailing newline.
No wall clock and no random are used, so a regenerated index is byte-identical.
Referenced facet codes are validated against the vocabularies that are present
(`industry.yaml` is required; `clusters.yaml`, `compositional-roles.yaml` and
`link-types.yaml` are validated when present); an unknown code exits non-zero.

### 3. query.py

    python tools/query.py [--index <path>] [filters]
    python tools/query.py --list-facets

Filters, all combinable with AND: `--industry CODE`, `--cluster CODE`,
`--role Rn`, `--origin internal|external`, `--link-type TYPE`, `--group NAME`.
It prints each matching entry (ref, origin, name, industry) and a count line.
`--list-facets` prints the totals and the five histograms instead.

A query over valid values always exits 0, even when nothing matches. A flag
value not present in the index (unknown industry, cluster, role, origin, link
type or group) exits non-zero with a message that lists the known values.

### 4. instantiate.py (the B6 button)

    python tools/instantiate.py --external <ACRONYM-or-NAME> --tenant <name> --at <ISO8601>
                                [--profile vercy-baseline]
                                [--registry <root>] [--write]
                                [--out-entry <path>] [--out-manifest <path>] [--print]

The external-to-internal transform: the single deterministic operation that
promotes one external standard (one row of `external/external-standards.csv`)
into an internal tenant meta-model, a first-class MMDG node the resolver can
compose, plus an instantiation manifest that records how the crossing was made.
It is the owner's formula made one step: `external-to-internal = Extension-Model
+ Policy-Consistency + Data-Mastership`, composed by ARCH-016. The normative
account is `transform/EXTERNAL-TO-INTERNAL.md`; the default overlay is
`transform/policy-profiles/vercy-baseline.yaml`.

It resolves `--external` to exactly one catalogue row by Acronym or Name
(case-insensitive exact; zero or more than one match is a hard error; `--standard`
is accepted as an alias of `--external`), reads the policy profile, and emits two
artifacts. The internal entry (`entries/<id>.yaml`, valid against
`schema/registry-node.schema.json` v0.3) is a complete Model Registration Record:
`kind` domain, `role` core, `origin` internal, `status` draft, `version` 0.1.0,
stewarded by the tenant, its `industry` inherited from the row verbatim, its
`source.repository` the external `SpecificationSourceURL` (the master per
ARCH-018), and the new v0.3 fields `tenant`, `derived_from`, `external_binding`
and `applied_policies` filled. The manifest
(`instantiations/<id>.manifest.json`, valid against
`schema/instantiation-manifest.schema.json`) records the `external_ref`, the
`external_binding`, the `mastership` stanza (system of record the external
source, inbound flow, per IC-1 and ARCH-018), the `applied_policies` (the IC-1 to
IC-8 controls and the profile policies, in order), the `delegation_tier` (T1 for
a fresh instantiation), the `lineage`, and the deterministic
`semantic_fingerprint`. Both are validated before anything is written.

**The mapping.** The standard's registry classification settles the binding.
`DefaultLinkType` maps to `external_binding.link_type` (EMBED to embed, REFERENCE
to reference, MIX-IN to mixin, ALIGN to align, EXTEND to extend, COMPOSE to
reference, N/A to annotate) and `CompositionalRole` maps to
`external_binding.composition_kind` (R1 value_object, R2 and R3 code, R4 entity,
R5 facet, R6 and R7 entity, R8 attribute). The AISMM conditional applies last: a
`value_object` forces `link_type` `embed`.

**The Semantic Package.** `external_binding.semantic_package` names the IMPORTED
external unit per Extension-Model, not the fresh internal consumer: it is
`<standard-slug>@<external-version>`, where the slug is drawn from the external
Acronym (falling back to the Name) and the version is the external `Year`
(`unversioned` when the row has no Year). For FHIR this is `fhir@<year>`, never
the internal `acme.fhir@0.1.0`.

**Output routing.** With no output flag the tool writes the pair into the
registry (`entries/<id>.yaml` and `instantiations/<id>.manifest.json`, creating
`instantiations/` if needed); `--write` is the explicit form of that default.
`--out-entry` / `--out-manifest` redirect to given paths, and `--print` writes
both to stdout and nothing to disk. This registry-write default is the mode
`ci/check_instantiations.py` replays to prove the committed fixtures are exactly
what the tool emits.

**Worked example.** Instantiate HL7 FHIR for tenant `acme` at a fixed timestamp:

    python tools/instantiate.py --external FHIR --tenant acme --at 2026-08-10T00:00:00Z

FHIR is classified `R4` / `REFERENCE` in the catalogue, so the binding resolves
deterministically to `composition_kind` entity and `link_type` reference (no
value-object override applies); the `healthcare-life-sciences` industry facet is
inherited from the row verbatim; `source.repository` is the FHIR specification
URL, the master per ARCH-018; and the new id is `acme.fhir`. To commit a real
instantiation, run the tool, then `tools/build_index.py` to refresh the index,
then regenerate the resolver fixtures under `examples/expected/` (adding any
entry changes the pack's registry-wide coverage line, the ordinary consequence
of registering a new model), and commit the entry, the manifest and the
refreshed artifacts together. The example fixtures are generated this way, never
hand-written.

**Determinism.** The transform reads no wall clock (the timestamp is the required
`--at` argument) and no randomness. The `internal_id`, the `semantic_fingerprint`
and the `instantiation_id` are deterministic hashes over canonical content: the
`internal_id` and `semantic_fingerprint` key off the resolved catalogue row
rather than the raw `--external` spelling, and the `instantiation_id` keys off
the tenant, the resolved `registry_ref`, the profile and the `--at` timestamp so
distinct instantiation events carry distinct ids. Key order is fixed, and each
artifact ends with a trailing newline (the manifest JSON with sorted keys and
two-space indent). Re-running with the same inputs yields a byte-identical entry
and manifest, which is what `ci/check_instantiations.py` asserts by replaying the
tool into a throwaway copy of the tree and byte-comparing.

## Determinism guarantee

Both build steps are pure functions of their inputs. There is no wall clock, no
random, and no environment dependence. Sort order is fixed everywhere: the CSV
rows by `(Group, Acronym, Name)`, the index entries by `(ref, origin)`, the
histogram and JSON keys by sort. Regenerating either artefact from unchanged
inputs produces byte-identical output, which is what a zero-change CI check
asserts.

## How CI uses it

CI runs the pipeline and then checks that the committed artefacts are exactly
what the tools produce from the committed inputs. `ci/check_facets.py`
regenerates `external/external-standards.csv` and `index/unified-index.json`
into a scratch location (or re-runs the tools with `--root`) and compares the
bytes against the committed files; a mismatch fails the check. It also validates
each external CSV row against `schema/external-standard.schema.json` and confirms
every facet code in the index resolves to a vocabulary entry. Because the tools
are deterministic, this check is stable: it passes only when the generated
artefacts are in sync with the source catalogue, the group map and the facet
vocabularies. The four pre-existing checks (`check_schema`, `check_graph`,
`check_resolve`, `check_zero_change`) and the resolver are untouched and keep
passing.
