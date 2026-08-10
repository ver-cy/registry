# Facet vocabularies

This directory holds the facet vocabularies of the unified registry. A facet is a
controlled axis of classification that applies to every entry, whether the entry
is an INTERNAL meta-model (an MMDG node under `entries/`) or an EXTERNAL standard
(a row of `external/external-standards.csv`). The registry uses two orthogonal
facet axes.

## Two orthogonal axes

- **Cluster: what a thing is.** The ontological kind of the entity, drawn from the
  fifteen world-models clusters (see `clusters.yaml`). Terrain, an organization, a
  payment, a record of account: cluster names the kind. Cluster is the primary
  facet for internal meta-models and an optional facet for external standards in
  v0.2. See ARCH-002 and ARCH-003 for the corpus these clusters come from.
- **Industry: which sector uses or governs it.** The sector of activity that uses
  or governs the entity, drawn from the Vercy industry vocabulary (see
  `industry.yaml`). Healthcare, financial services, transport: industry names the
  sector.

The two axes are independent. A geospatial coordinate reference system is the same
kind of thing (a reference system) whether it is used in agriculture, aviation, or
government; its cluster is fixed while its industry set varies. Both axes apply to
both entry classes: every external standard inherits its industry codes from its
Group through `group-industry-map.csv`, and internal meta-models carry `industry[]`
and `cluster[]` in their own entry files.

## Industry is multi-valued and swappable

Industry is multi-valued: one entry may carry several industry codes. The
vocabulary is ISIC Rev.4 aligned for neutrality (ISIC is the UN global reference;
NACE, NAICS, and GICS map onto it), and it is swappable: entries reference codes by
scheme id, so a later switch to raw ISIC, NACE, NAICS, or GICS is a re-map of
`industry.yaml` plus the Group map, not a schema change. Verticals are sectors;
horizontals are cross-cutting technical capabilities.

State and Polity is not a privileged axis. In the industry vocabulary it is one
vertical among many, `government-public-sector`; in the cluster vocabulary it is
one cluster among fifteen, `polity`. The registry treats the state as one domain
of activity, not the frame of the whole.

## How an external standard composes

Two further vocabularies describe HOW an external standard composes into the graph
of internal meta-models, rather than what it is or which sector owns it:

- `compositional-roles.yaml` gives the eight roles R1 to R8 from
  Meta-Model-Composition (ARCH-016): the kind of building block a standard is
  (value object, code list, identifier scheme, entity model, cross-cutting facet,
  aggregate, upper ontology, infrastructure).
- `link-types.yaml` gives the composition mechanisms (EMBED, REFERENCE, MIX-IN,
  COMPOSE, ALIGN, EXTEND, and the literal N/A) by which an internal node draws on a
  standard. Each role carries a default link type.

This classification is informative guidance. A role suggests a default link type;
an actual instantiation is settled by the future external-to-internal transform,
which is out of scope here.

## Vocabulary files

- `clusters.yaml` : ontological cluster facet, the fifteen world-models clusters
  (scheme `vercy-cluster`). The "what a thing is" axis.
- `industry.yaml` : industry facet, ISIC-aligned verticals and cross-cutting
  horizontals (scheme `vercy-industry`). The "which sector" axis.
- `compositional-roles.yaml` : the eight R1 to R8 roles from ARCH-016, with default
  link types and catalogue counts (scheme `vercy-compositional-role`).
- `link-types.yaml` : the ARCH-016 composition mechanisms plus N/A (scheme
  `vercy-link-type`).
- `group-industry-map.csv` : maps each external-registry Group to one or more
  industry codes, so external standards inherit industry from their Group.
