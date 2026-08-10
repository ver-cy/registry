# The external standards catalogue

This directory holds the discovery catalogue of external standards: the reference
standards the world already publishes, faceted so they can be found, compared, and
one day drawn into the graph. It is the second of the two entry classes of the
unified registry. The first class, the internal meta-models under `entries/`, are
MMDG nodes: few, governed, versioned, and joined by typed edges. This class is the
opposite in every dimension: many, ungoverned by this registry, and not part of the
graph. An external standard is a citation, not a node. It becomes an MMDG node only
when it is instantiated by a future external-to-internal transform, which is out of
scope here. Until then this is a discovery catalogue and nothing more.

## The two files

- `external-models.source.csv` is the authored source catalogue: 1180 rows, one per
  standard, fifteen columns fixed at authoring time (`Group`, `Name`, `Acronym`,
  `SpecificationSourceURL`, `Category`, `ParentModel`, `SimilarModels`,
  `Maintainer`, `Format`, `Status`, `NamespaceURI`, `Year`, `Notes`,
  `CompositionalRole`, `DefaultLinkType`). This file is edited by hand; it is the
  input, never a generated artifact.
- `external-standards.csv` is the generated catalogue: every source row, verbatim,
  with two facet columns appended. It is produced by `tools/import_external.py` and
  must never be edited by hand, because it is regenerated and byte-compared in CI.

## The columns

The generated `external-standards.csv` carries all fifteen source columns in their
original order, then two columns the importer adds:

- `Origin` is the origin facet. For every row in this catalogue it is the constant
  `external`: these standards are authored outside the registry's governance domain.
  The column exists so the origin facet reads uniformly across both entry classes
  (internal meta-models carry `origin: internal` in their entry files), and so a
  unified query can filter by origin without special-casing the two files.
- `Industry` is the sector axis. It holds the semicolon-joined vercy-industry codes
  the row inherits from its `Group` through `facets/group-industry-map.csv`. Every
  external standard therefore carries at least one industry code, assigned once per
  Group rather than per row, so the mapping is small (37 Groups) and auditable. The
  codes are drawn from and validated against `facets/industry.yaml`.

The cluster axis (what a standard is, the fifteen ontological clusters) is optional
for external standards in v0.2 and is not populated by the importer; it is reserved
for the instantiation transform. `CompositionalRole` (R1 to R8 of ARCH-016) and
`DefaultLinkType` (`EMBED`, `REFERENCE`, `MIX-IN`, `COMPOSE`, `ALIGN`, `EXTEND`, or
the literal `N/A`) are carried through from the source and describe how a standard
of that role would compose into the graph of internal meta-models. That guidance is
informative; the actual link is settled by the instantiation transform, not here.

## How it is generated

```
external-models.source.csv  +  facets/group-industry-map.csv
                         |
                 tools/import_external.py
                         |
                         v
              external-standards.csv   (source columns + Origin + Industry)
```

`tools/import_external.py` reads the source catalogue and the Group map, checks that
every `Group` in the source appears in the map and that every mapped code is a known
industry code, appends `Origin` and `Industry`, sorts the rows by `Group` then
`Acronym` then `Name`, and writes the result with a fixed CSV dialect (LF line
terminator, minimal quoting, stable column order). The build is deterministic:
re-running it yields a byte-identical file, which is exactly what the facet CI check
relies on. The tool exits non-zero with a clear diagnostic when a Group is missing
from the map or a mapped code is unknown, so a drifted source or map fails closed
rather than producing a silently wrong catalogue.

## Validation

Each generated row projects to a JSON object (the source headers lower-snake-cased,
plus `origin`, `industry`, and the optional `cluster`) and validates against
`schema/external-standard.schema.json`. That schema is deliberately distinct from
the internal `registry-node.schema.json`: an external standard carries the catalogue
columns and the two facet axes but none of the MMDG node profile (no `csn`, `role`,
`exports`, `requires`, `sync_contract`, or edges), which is the schema-level
statement that a reference is not a node.
