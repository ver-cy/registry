#!/usr/bin/env python3
"""run: the ELMM registry admission gate, all checks in order.

Runs, in order:

    check_schema         V0 schema validation (ELMM-I8, ELMM-I14)
    check_graph          MMDG graph integrity (ELMM-I11, I16, I17, I18, I19)
    check_resolve        resolver determinism and output validity (ELMM-I23, I30)
    check_zero_change    the zero-change registration guarantee (ELMM-I7, ELMM-I44)
    check_facets         facet vocabulary and generated-artifact integrity (ARCH-017)
    check_instantiations B6 external-to-internal transform integrity (ARCH-014/016/018, IC-1)
    check_conventions    scaffold-convention integrity (S1 header + no-date rule, S2)
    check_taint          canonical-identity neutrality, no commercial coupling (ELMM-I39)

The first four are the walking-skeleton kernel checks. check_facets is the
unified-registry extension: it guards the two orthogonal facet axes (cluster and
industry) over both entry classes and proves the two generated artifacts
(external/external-standards.csv, index/unified-index.json) are current.
check_instantiations is the B6 extension: it guards each committed
external-to-internal instantiation (schema, internal entry, external resolution,
policy overlay, industry inheritance, IC-1 mastership) and proves the transform
is replayable byte for byte. It passes vacuously until the first instantiation
is committed. check_conventions is the standard-scaffold extension: it gives the
S1/S2 backlog items their acceptance tests, guarding the artifact header schema
(a valid JSON Schema), the no-date-in-filename rule over entries/, mmdg/ and
schema/, and the documented-conventions readme. It passes with a note while a
convention does not yet apply.

Prints a per-check summary and exits non-zero if any check failed. This is the
fail-closed admission gate on the registry write path (ELMM-I39): the whole
gate is CI, and CI is this script.

Usage:
    python run.py [--root <registry-root>]
"""

import argparse
import os
import subprocess
import sys

CHECKS = (
    "check_schema.py",
    "check_graph.py",
    "check_resolve.py",
    "check_zero_change.py",
    "check_facets.py",
    "check_instantiations.py",
    "check_conventions.py",
    "check_taint.py",
    "check_catalogue_contracts.py",
)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run all ELMM registry checks")
    parser.add_argument("--root", default=None, help="registry root directory")
    args = parser.parse_args(argv)

    ci_dir = os.path.dirname(os.path.abspath(__file__))
    common_args = ["--root", args.root] if args.root else []

    results = []
    for check in CHECKS:
        script = os.path.join(ci_dir, check)
        sys.stdout.write("\n" + "=" * 72 + "\n")
        sys.stdout.write("RUN  " + check + "\n")
        sys.stdout.write("=" * 72 + "\n")
        sys.stdout.flush()
        proc = subprocess.run([sys.executable, script] + common_args)
        results.append((check, proc.returncode))

    sys.stdout.write("\n" + "=" * 72 + "\n")
    sys.stdout.write("SUMMARY\n")
    sys.stdout.write("=" * 72 + "\n")
    failed = 0
    for check, code in results:
        status = "PASS" if code == 0 else "FAIL"
        if code != 0:
            failed += 1
        sys.stdout.write("  " + status + "  " + check + "\n")
    total = len(results)
    sys.stdout.write(
        "\n" + str(total - failed) + " of " + str(total) + " checks passed"
        + ("" if failed == 0 else ", " + str(failed) + " failed") + "\n"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
