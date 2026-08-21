#!/usr/bin/env python3
"""Validate the registry-first vNext contracts and worked examples."""

import json
import os
import subprocess
import sys
import tempfile

import yaml
from jsonschema import Draft202012Validator, FormatChecker


CASES = (
    ("schema/catalogue-specification.schema.json", "examples/catalogue/example-model.specification.yaml"),
    ("schema/patch-package.schema.json", "examples/catalogue/example.patch.yaml"),
    ("schema/dimension-owner-package.schema.json", "examples/catalogue/example.dimension.yaml"),
    ("schema/adapter-descriptor.schema.json", "examples/catalogue/yaml.adapter.yaml"),
    ("schema/deployment-profile.schema.json", "examples/catalogue/git-yaml.profile.yaml"),
)


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    print("check_catalogue_contracts: vNext schemas and examples")
    for schema_rel, example_rel in CASES:
        with open(os.path.join(root, schema_rel), encoding="utf-8") as handle:
            schema = json.load(handle)
        Draft202012Validator.check_schema(schema)
        with open(os.path.join(root, example_rel), encoding="utf-8") as handle:
            example = yaml.safe_load(handle)
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(example)
        print("  ok ", example_rel, "valid against", schema_rel)
    with tempfile.TemporaryDirectory() as temp:
        source = os.path.join(root, "examples/catalogue/example-model.specification.yaml")
        subprocess.run(
            [sys.executable, os.path.join(root, "tools/build_ai_package.py"), source, temp],
            check=True,
            capture_output=True,
            text=True,
        )
        generated = os.path.join(temp, "example.task-context", "1.0.0")
        committed = os.path.join(root, "catalogue", "example.task-context", "1.0.0")
        for name in ("ai.yaml", "AGENTS.md"):
            with open(os.path.join(generated, name), "rb") as left:
                generated_bytes = left.read()
            with open(os.path.join(committed, name), "rb") as right:
                committed_bytes = right.read()
            if generated_bytes != committed_bytes:
                raise AssertionError("generated catalogue artifact drift: " + name)
        print("  ok  immutable AI package regenerates byte-identical")
    print("check_catalogue_contracts: PASS ({} contracts)".format(len(CASES)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
