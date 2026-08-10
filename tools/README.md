# Registry tooling

Three deterministic scripts build and query the unified registry. They are
stdlib plus PyYAML (build steps) and jsonschema is not required here. Every
script locates the registry root from its own file location (the parent of
`tools/`, matching the `ci/_common.py` convention), so it runs from any working
directory and on a copied tree. Every script exits non-zero with a diagnostic on
`stderr` when an input is missing or a facet code is unknown.

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
