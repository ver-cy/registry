#!/usr/bin/env python3
"""Build the deterministic Bitrix catalogue import used by ver.cy.

The public model catalogue and the interoperability registry intentionally live
in separate Bitrix information blocks.  This keeps subject meta-models distinct
from formats, ontologies, interfaces and other external alignment targets.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path


SITE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_UNIFIED = (
    SITE_ROOT.parent
    / "ver-cy"
    / "world-models"
    / "planning"
    / "VERCY-UNIFIED-MEGA-REGISTRY.csv"
)
DEFAULT_CATALOGUE = SITE_ROOT / "models" / "catalog-index.json"
DEFAULT_OUTPUT = SITE_ROOT / "tools" / "server" / "vercy-catalog-import.json"

CATEGORY_LABELS = {
    "ACT": "Activities and processes",
    "SOC": "Society, people and institutions",
    "PHY": "Physical world and living systems",
    "INF": "Information and virtual systems",
    "XCT": "Cross-cutting context",
}

STOP_WORDS = {"a", "an", "and", "for", "in", "of", "or", "the", "to", "with"}


def split_values(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in re.split(r"\s*;\s*", value) if part.strip()]


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value.lower()).strip("-")
    return slug or "model"


def stable_unique(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = value.casefold()
        if value and key not in seen:
            result.append(value)
            seen.add(key)
    return result


def model_tags(row: dict[str, str]) -> list[str]:
    words = re.findall(r"[a-z0-9]+", row["name"].lower())
    words = [word for word in words if word not in STOP_WORDS and len(word) > 1]
    domains = [value.lower() for value in split_values(row.get("domain_tags"))]
    alternatives = [value.lower() for value in split_values(row.get("alternate_names"))]
    return stable_unique(words + domains + alternatives)


def navigation_category(nav_path: str) -> str:
    match = re.search(r"(?:^|/)NAV\.([A-Z]+)", nav_path or "")
    return CATEGORY_LABELS.get(match.group(1), "World model") if match else "World model"


def alias_index(catalogue: list[dict]) -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = {}
    for item in catalogue:
        match = re.match(r"world\.([a-z]+\d+)(?:-|$)", item.get("id", ""), re.I)
        if match:
            result.setdefault(match.group(1).upper(), []).append(item)
    return result


def first_legacy_card(row: dict[str, str], by_alias: dict[str, list[dict]]) -> dict | None:
    for alias in split_values(row.get("legacy_alias")):
        clean = alias.strip().upper()
        if clean in by_alias:
            return by_alias[clean][0]
    return None


def world_record(row: dict[str, str], legacy_card: dict | None) -> dict:
    has_previous_spec = row.get("status") == "described-previous-version" and legacy_card is not None
    code = f"{row['model_id'].lower()}-{slugify(row['name'])}"
    page_url = legacy_card["url"] if has_previous_spec else f"/models/{code}/"
    version = legacy_card.get("version", "") if has_previous_spec else ""
    source_url = (legacy_card or {}).get("sourceUrl") or row.get("source_url", "")
    legacy_aliases = split_values(row.get("legacy_alias"))

    return {
        "registry_id": row["registry_id"],
        "record_plane": row["record_plane"],
        "model_id": row["model_id"],
        "name": row["name"],
        "alternate_names": split_values(row.get("alternate_names")),
        "code": code,
        "entry_kind": row.get("entry_kind", "standalone-mm"),
        "status": "legacy" if has_previous_spec else "todo",
        "status_raw": row.get("status", ""),
        "spec_available": has_previous_spec,
        "version": version,
        "family": "World Models",
        "category": navigation_category(row.get("nav_path", "")),
        "industry": ["Cross-industry"],
        "domain": split_values(row.get("domain_tags")),
        "tags": model_tags(row),
        "page_url": page_url,
        "source_url": source_url,
        "spec_url": f"{page_url}spec.yaml" if has_previous_spec else "",
        "agents_url": f"{page_url}AGENTS.md" if has_previous_spec else "",
        "yaml_url": f"{page_url}spec.yaml" if has_previous_spec else "",
        "nav_path": row.get("nav_path", ""),
        "legacy_alias": legacy_aliases,
        "existing_spec_ref": split_values(row.get("existing_spec_ref")),
        "parent_ids": split_values(row.get("parent_ids")),
        "contains_ids": split_values(row.get("contains_ids")),
        "aligned_model_ids": split_values(row.get("aligned_model_ids")),
        "purpose": row.get("purpose", ""),
        "owner": row.get("owner_or_maintainer", ""),
        "review_state": row.get("review_state", ""),
        "origin": row.get("origin", ""),
        "namespace_uri": row.get("namespace_uri", ""),
        "source_version": row.get("source_version_or_year", ""),
        "source_group": row.get("source_group", ""),
        "source_category": row.get("source_category", ""),
        "source_format": row.get("source_format", ""),
        "composition_role": split_values(row.get("composition_role")),
        "default_link_type": row.get("default_link_type", ""),
        "priority_wave": int(row["priority_wave"]) if row.get("priority_wave", "").isdigit() else None,
        "priority_score": float(row["priority_score"]) if row.get("priority_score") else None,
        "priority_confidence": row.get("priority_confidence", ""),
        "priority_rationale": row.get("priority_rationale", ""),
        "relations_ref": row.get("relations_ref", ""),
        "provenance": row.get("provenance", ""),
    }


def vercy_example(item: dict) -> dict:
    is_aismm = item["id"] == "vercy.aismm"
    model_id = "AISMM" if is_aismm else "PLMM"
    purpose = (
        "Connected software context for AI agents and software delivery."
        if is_aismm
        else "Product landscape, portfolio and capability context."
    )
    return {
        "registry_id": f"vr.{item['id']}",
        "record_plane": "world-model",
        "model_id": model_id,
        "name": item["name"],
        "alternate_names": [],
        "code": item["url"].strip("/").split("/")[-1],
        "entry_kind": "reference-assembly",
        "status": "published" if is_aismm else "legacy",
        "status_raw": item.get("status", ""),
        "spec_available": True,
        "version": item.get("version", ""),
        "family": item.get("family", "Vercy examples"),
        "category": item.get("category", "Reference assembly"),
        "industry": item.get("industry", ["Cross-industry"]),
        "domain": item.get("domain", []),
        "tags": item.get("tags", []),
        "page_url": item["url"],
        "source_url": item.get("sourceUrl", ""),
        "spec_url": f"{item['url']}spec.yaml",
        "agents_url": f"{item['url']}AGENTS.md",
        "yaml_url": f"{item['url']}spec.yaml",
        "nav_path": "NAV.INF.SFT" if is_aismm else "NAV.INF.PRD",
        "legacy_alias": [],
        "existing_spec_ref": [],
        "parent_ids": [],
        "contains_ids": [],
        "aligned_model_ids": [],
        "purpose": purpose,
        "owner": "Vercy maintainers",
        "review_state": "published" if is_aismm else "migration-boundary-review",
        "origin": "vercy-current-site",
        "namespace_uri": "https://ver.cy/models/",
        "source_version": item.get("version", ""),
        "source_group": "Vercy",
        "source_category": item.get("category", ""),
        "source_format": "Vercy specification",
        "composition_role": [],
        "default_link_type": "TYPED-EDGES",
        "priority_wave": 0,
        "priority_score": 100 if is_aismm else 80,
        "priority_confidence": "high",
        "priority_rationale": "Current Vercy reference assembly.",
        "relations_ref": "",
        "provenance": "Current ver.cy catalogue",
    }


def interoperability_record(row: dict[str, str]) -> dict:
    code = slugify(row["registry_id"])
    return {
        "registry_id": row["registry_id"],
        "record_plane": row["record_plane"],
        "model_id": row.get("model_id", ""),
        "name": row["name"],
        "alternate_names": split_values(row.get("alternate_names")),
        "code": code,
        "entry_kind": row.get("entry_kind", "external-reference"),
        "status": "reference",
        "status_raw": row.get("status", ""),
        "spec_available": False,
        "version": row.get("source_version_or_year", ""),
        "family": "Interoperability",
        "category": row.get("source_category") or row.get("entry_kind") or "External reference",
        "industry": [],
        "domain": split_values(row.get("domain_tags")),
        "tags": model_tags(row),
        "page_url": "",
        "source_url": row.get("source_url", ""),
        "spec_url": "",
        "agents_url": "",
        "yaml_url": "",
        "nav_path": row.get("nav_path", ""),
        "legacy_alias": split_values(row.get("legacy_alias")),
        "existing_spec_ref": split_values(row.get("existing_spec_ref")),
        "parent_ids": split_values(row.get("parent_ids")),
        "contains_ids": split_values(row.get("contains_ids")),
        "aligned_model_ids": split_values(row.get("aligned_model_ids")),
        "purpose": row.get("purpose", ""),
        "owner": row.get("owner_or_maintainer", ""),
        "review_state": row.get("review_state", ""),
        "origin": row.get("origin", ""),
        "namespace_uri": row.get("namespace_uri", ""),
        "source_version": row.get("source_version_or_year", ""),
        "source_group": row.get("source_group", ""),
        "source_category": row.get("source_category", ""),
        "source_format": row.get("source_format", ""),
        "composition_role": split_values(row.get("composition_role")),
        "default_link_type": row.get("default_link_type", ""),
        "priority_wave": int(row["priority_wave"]) if row.get("priority_wave", "").isdigit() else None,
        "priority_score": float(row["priority_score"]) if row.get("priority_score") else None,
        "priority_confidence": row.get("priority_confidence", ""),
        "priority_rationale": row.get("priority_rationale", ""),
        "relations_ref": row.get("relations_ref", ""),
        "provenance": row.get("provenance", ""),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--unified", type=Path, default=DEFAULT_UNIFIED)
    parser.add_argument("--catalogue", type=Path, default=DEFAULT_CATALOGUE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    with args.catalogue.open(encoding="utf-8") as handle:
        catalogue = json.load(handle)
    with args.unified.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    by_alias = alias_index(catalogue)
    world_rows = [row for row in rows if row["record_plane"] == "world-model"]
    external_rows = [row for row in rows if row["record_plane"] != "world-model"]
    models = [world_record(row, first_legacy_card(row, by_alias)) for row in world_rows]
    examples = [item for item in catalogue if item.get("id") in {"vercy.aismm", "vercy.plmm"}]
    models.extend(vercy_example(item) for item in examples)
    interoperability = [interoperability_record(row) for row in external_rows]

    registry_ids = [item["registry_id"] for item in models + interoperability]
    if len(registry_ids) != len(set(registry_ids)):
        raise SystemExit("duplicate registry_id in generated import")
    model_codes = [item["code"] for item in models]
    if len(model_codes) != len(set(model_codes)):
        raise SystemExit("duplicate model code in generated import")
    if len(models) != 403 or len(interoperability) != 1180:
        raise SystemExit(
            f"unexpected registry sizes: models={len(models)}, interoperability={len(interoperability)}"
        )
    missing_previous = [
        item["model_id"]
        for item in models
        if item["status_raw"] == "described-previous-version" and not item["spec_available"]
    ]
    if missing_previous:
        raise SystemExit(f"previous specifications did not map to site cards: {missing_previous}")

    batch = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = {
        "schema": "https://ver.cy/schemas/bitrix-catalog-import/v1",
        "generated_at": batch,
        "source": "VERCY-UNIFIED-MEGA-REGISTRY.csv",
        "counts": {
            "models": len(models),
            "model_todo": sum(item["status"] == "todo" for item in models),
            "model_available": sum(item["spec_available"] for item in models),
            "interoperability": len(interoperability),
        },
        "models": sorted(models, key=lambda item: (item["priority_wave"] or 99, item["name"].casefold())),
        "interoperability": sorted(interoperability, key=lambda item: item["name"].casefold()),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["counts"], ensure_ascii=False))


if __name__ == "__main__":
    main()
