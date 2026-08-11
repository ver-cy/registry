# Vercy scaffold conventions (candidate Meta-Universe change requests)

Three reusable scaffold conventions for every Vercy-family meta-model. Each is
written here as a candidate change request against the Meta-Universe standard,
with a crisp rule and its rationale, cited by ID and bound by reference. These
are filed as change requests and applied first in `vercy.collmm` as the
reference model. The published standard docs (ARCH-002, ARCH-003, ARCH-017 and
the rest) are NOT edited here: this file is the proposal register, the standard
is amended through its own change process.

Machinery is cited by ID and bound by reference, not restated: ARCH-002
(versioning and lifecycle), ARCH-003 (naming and identity), ARCH-009 (semantic
fingerprint), ARCH-016 (composition roles), ARCH-017 (traversal and bootstrap),
ARCH-018 (data mastership), CORE-009 (projection), CON-6 (versioning and change
history), IC-1 (one master per dataset), IC-4 (security-critical changes), IC-7
(owner-gated reads), IC-8 (append-only history).

## Change request list

| CR | Rule | Lands in | Reference artifact |
|----|------|----------|--------------------|
| CR-A | Standard artifact header block, plus dates SHALL NOT appear in filenames | `registry/schema/artifact-header.schema.json` + an ARCH-003 naming clause | `vercy.collmm` layer headers |
| CR-B | `AGENTS.md` is the canonical ARCH-017 root bootstrap, required at new roots, superseding `BOOTSTRAP.md` | ARCH-017 amendment | `collmm/AGENTS.md` |
| CR-C | `/.vercy/` holds root-level meta-artifacts so the root stays clean | ARCH-017 layout rule | `collmm/.vercy/` bundle |

---

## CR-A: Artifact header block and no dates in filenames

**Rule.** Every governed artifact (every Finding file, layer file, bundle README
and root doc) carries a front-matter header block at its top, validated against
`registry/schema/artifact-header.schema.json`. The block declares a stable `id`,
a `title`, a `status` (one of draft, active, deprecated, retired), and a
`change_history` array of at least one entry, each entry carrying a `date`, an
`author` and a one-line `summary`; `owners` and `source_layer` are optional. The
paired naming clause, a candidate ARCH-003 clause: dates SHALL NOT appear in
filenames; the date, the authors and the change history live in the artifact
header block. Filenames carry the stable ARCH-003 identifier and the semantic
name only, never a date and never a version.

**Rationale.** The header block is the artifact-level face of ARCH-002
(versioning and lifecycle) and CON-6 (versioning and change history), and its
`change_history` is append-only per IC-8: entries are added, never rewritten or
removed, so the header is the artifact's own memory. Because the `id` is stable
and date-free, superseding an artifact does not rename its file: it flips
`status` to deprecated and appends a `change_history` entry, which preserves the
ARCH-009 fingerprint over canonical form (a byte hash is never a semantic pin).
The `id`, `title` and `status` fields are IC-4 adjacent and do not ride the
auto-approval lane. This is the smallest change and a prerequisite for CR-C
(files that move into `/.vercy/` must keep stable, date-free ids so nothing
becomes unreachable), so it goes first. The corpus violates the naming clause
today: the deployment AISMM instance embeds the date in the filename with the
`{kind}-{YYMMDDNNNNN}-{memo}.md` pattern; that pattern is retired in favor of
the header.

## CR-B: AGENTS.md is the canonical root bootstrap

**Rule.** `AGENTS.md` is the single canonical ARCH-017 root bootstrap for a
vercy-family meta-model, required at the root of every NEW model root. It folds
the ARCH-017 traversal contract into one file and states, per the ARCH-017
structure: (a) that this is a vercy-family meta-model and which Subject or Object
it models; (b) the specification it conforms to, by registry id and version;
(c) reading order for humans and for agents; (d) the manifest table of what
lives where; (e) the traversal rules (identity, edges, mastership lives in
`sources.yaml` not in edges, freshness, snapshots); (f) pointers to
`sources.yaml` (inbound masters) and `sinks.yaml` (outbound publication).
`AGENTS.md` supersedes the ad hoc `BOOTSTRAP.md` name. Migration: existing
`BOOTSTRAP.md` content folds into `AGENTS.md`; retrofit is lazy (each model gets
its `AGENTS.md` as it is next touched), with no repo-wide rename campaign and no
new roots without one.

**Rationale.** ARCH-017 already defines the traversal entry point, its two-
audience reading order, and its manifest of what lives where; the pattern is
demonstrated at `registry/BOOTSTRAP.md`. What is missing is the standard name,
universal coverage and one normative template. `AGENTS.md` is now the broad
ecosystem convention for the first file an automated consumer reads, so making
it the one canonical name gives a model root a single bootstrap instead of two
and removes the `BOOTSTRAP.md` / `AGENTS.md` split. Scope discipline keeps the
change cheap: required at new roots only.

## CR-C: the /.vercy/ root meta-artifacts bundle

**Rule.** A reserved dot-directory `/.vercy/` holds a model's root-level meta-
artifacts so the root stays clean and navigable. The stays-at-root set is
exactly `AGENTS.md`, `README.md`, `manifest.yaml`, `sources.yaml`, `sinks.yaml`
and `LICENSE`. Everything else that would otherwise sit at the root moves into
`/.vercy/`: `CHANGELOG.md`, `CONTRIBUTING.md`, `GOVERNANCE.md`, `SECURITY.md`,
`CODE_OF_CONDUCT.md`, `STATUS.md`, roadmaps, requirement indexes, `spec-index.yaml`,
`llms.txt` and any other governance-and-process paperwork. The `AGENTS.md`
manifest table lists the moved files at their new paths so nothing becomes
unreachable.

**Rationale.** Model roots accumulate governance and process paperwork and stop
being navigable; a dot-directory sorts aside and reads as infrastructure, not
content. The load-bearing constraint is that `manifest.yaml` and `sources.yaml`
must not move: agents read `AGENTS.md`, then the manifest, then `sources.yaml`
before touching content, and CON-1 intake consumes the manifest and the ARCH-018
Mastership Register directly, so moving them would break the bootstrap chain.
`sinks.yaml`, the outbound publication register that is a CORE-009 and IC-7
peer of `sources.yaml`, stays at root for the same reason. This is a net-new
pattern: no root-bundle convention exists in the corpus today.

---

## Filing and application

These three are filed as candidate Meta-Universe change requests against the
standard. They are applied first in `vercy.collmm`, the reference model, which
ships under this scaffold: an `AGENTS.md` at root (CR-B), a `/.vercy/` bundle
holding `CHANGELOG.md`, `CONTRIBUTING.md` and other meta-artifacts while
`LICENSE` stays at root (CR-C), and each layer doc carrying a header block with a
`change_history` table that validates against
`registry/schema/artifact-header.schema.json` (CR-A). The published standard
documents are amended only through the standard's own change process, not in this
repository.
