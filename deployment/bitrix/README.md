# Bitrix catalogue projection for ver.cy

This directory versions the reproducible projection of the Vercy registry into
the shared Bitrix installation used by `https://ver.cy/`. Bitrix is a delivery
store and administration surface. It is not the semantic source of truth and
does not make a carrier, file format or interface part of a meta-model identity.

## Information blocks

The idempotent migration creates information-block type `vercy_registry` and
binds both blocks to Bitrix site `vc`:

| Code | Purpose | Production count on 2026-08-22 |
| --- | --- | ---: |
| `vercy_models` | Desired subject meta-models published at `/models/` | 403 |
| `vercy_interoperability` | External standards, schemas, ontologies and classifiers | 1,180 |

The separation is deliberate: an external standard can align with or be used by
a meta-model without being misrepresented as that subject model. Both blocks use
the same 42-property administrative vocabulary for stable identity, facets,
version/status, links, ownership, relations, priority and provenance.

Of the 403 public model entries, 264 are planned and carry `MODEL_STATUS=todo`.
The remaining 139 link to AISMM, PLMM or previous-version World Model
specifications. A TODO detail page never exposes invented YAML as a complete
specification.

## Source mapping

Files in this directory map to the ver.cy document root as follows:

| Repository file | Production path |
| --- | --- |
| `migrate-vercy-catalog.php` | `tools/server/migrate-vercy-catalog.php` |
| `inspect-vercy-catalog.php` | `tools/server/inspect-vercy-catalog.php` |
| `models-index.php` | `models/index.php` |
| `urlrewrite.php` | `urlrewrite.php` |
| `gen_sitemap.py` | `tools/gen_sitemap.py` |
| `run_catalog_migration.sh` | local operator helper under `tools/` |

`build_bitrix_catalog_import.py` deterministically joins the audited unified
mega-registry from `ver-cy/world-models` with the current site catalogue. It
emits `vercy-catalog-import.json`; that generated deployment payload is omitted
from Git because it is about 3 MB and can be reproduced from reviewed inputs.

Example build:

```bash
python deployment/bitrix/build_bitrix_catalog_import.py \
  --unified ../world-models/planning/VERCY-UNIFIED-MEGA-REGISTRY.csv \
  --catalogue /path/to/ver.cy/models/catalog-index.json \
  --output /path/to/ver.cy/tools/server/vercy-catalog-import.json
```

The generator fails closed unless it produces exactly 403 subject-model records,
1,180 interoperability records, 264 TODO entries and a unique stable identity for
every row.

## Runtime behavior

- `/models/` is server-rendered from `vercy_models` and exposes text plus family,
  category, industry, domain and status filters.
- `/models/?format=json` is the read-only JSON projection.
- `/models/{code}/` resolves planned records through Bitrix URL rewriting.
- Existing physical model directories take precedence, preserving their full
  specification, `AGENTS.md`, AI YAML and embedded constructor.
- The sitemap generator reads the import projection so dynamic TODO URLs are
  discoverable even though they have no physical directory.

Run the migration as the web-server user so Bitrix can invalidate managed cache.
The operator helper reads the existing server credential from the local secret
store, never from this repository. Production deployment must retain rollback
backups outside the document root.

Verified on 2026-08-22: repeated import created zero new records, updated the
expected 403 + 1,180 rows, deactivated zero rows, generated a 1,004-URL sitemap,
and passed all `check_aeo.sh` invariants.
