#!/usr/bin/env python3
"""Build immutable AI bootstrap artifacts from one catalogue specification."""

import argparse
import copy
import os
import sys

import yaml


def read_yaml(path):
    with open(path, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def dump_yaml(value):
    return yaml.safe_dump(value, allow_unicode=True, sort_keys=False, width=1000)


def ai_projection(specification):
    result = {
        "instruction_schema": "https://ver.cy/schema/ai-instruction/1.0.0",
        "source": {
            "catalogue_id": specification["identity"]["catalogue_id"],
            "version": specification["versioning"]["version"],
            "immutable_url": specification["versioning"]["immutable_url"],
            "fingerprint": specification["identity"].get("fingerprint"),
        },
        "agent_protocol": {
            "cold_start": [
                "Verify catalogue_id, version and fingerprint before using the model.",
                "Read service.canon, policies, processes, roles and access before model data.",
                "Traverse structure.bundles in declared order, then layers, findings, questions and artifacts.",
                "Resolve child-model references and master bindings; do not copy or override foreign ownership.",
                "Use only operations and deployment profiles declared by this pinned specification.",
            ],
            "write_guards": [
                "Write only to the declared authoritative master at the affected grain.",
                "Validate access, purpose, schema and policy before a mutation.",
                "Supersede or retire versioned data; do not silently rewrite published history.",
                "Record provenance, validation result and change event.",
            ],
            "refuse_when": [
                "The pinned specification or a required reference cannot be resolved.",
                "Mastership is absent, ambiguous or stale beyond the declared limit.",
                "The requested action is not allowed by the effective access and policy rules.",
                "A patch precondition or expected fingerprint does not match.",
            ],
        },
        "specification": copy.deepcopy(specification),
    }
    if result["source"]["fingerprint"] is None:
        del result["source"]["fingerprint"]
    return result


def agents_markdown(specification):
    identity = specification["identity"]
    service = specification["service"]
    profiles = service.get("supported_deployment_profiles", [])
    lines = [
        "# Agent bootstrap",
        "",
        "```yaml",
        "name: " + identity["name"],
        "catalogue_id: " + identity["catalogue_id"],
        "type: " + specification["classification"]["category"],
        "specification: " + service["agent_bootstrap"]["ai_instruction"],
        "storage_profiles:",
    ]
    lines.extend("  - " + value for value in profiles)
    lines.extend([
        "processes:",
        *["  - " + item["target"] for item in service["processes"]],
        "```",
        "",
        "Fetch the pinned AI instruction before reading or changing model data.",
        "",
    ])
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("specification")
    parser.add_argument("output_root")
    args = parser.parse_args(argv)
    spec = read_yaml(args.specification)
    catalogue_id = spec["identity"]["catalogue_id"]
    version = spec["versioning"]["version"]
    target = os.path.join(args.output_root, catalogue_id, version)
    os.makedirs(target, exist_ok=True)
    with open(os.path.join(target, "ai.yaml"), "w", encoding="utf-8", newline="\n") as handle:
        handle.write(dump_yaml(ai_projection(spec)))
    with open(os.path.join(target, "AGENTS.md"), "w", encoding="utf-8", newline="\n") as handle:
        handle.write(agents_markdown(spec))
    print(target)
    return 0


if __name__ == "__main__":
    sys.exit(main())

