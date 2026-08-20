#!/usr/bin/env python3
"""Validate the registry-first vNext contracts and worked examples."""

import json
import os
import sys

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
    print("check_catalogue_contracts: PASS ({} contracts)".format(len(CASES)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

