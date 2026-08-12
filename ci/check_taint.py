#!/usr/bin/env python3
"""check_taint: canonical-identity neutrality of the open standard.

The eighth admission check. The Vercy standard is an open standard that must
carry zero commercial coupling: no commercial account, product or vendor name
may appear in a canonical-identity position (a schema $id or title, the value
of an id / model_id / csn / namespace / display_alias key, or a file or
directory name under registry/ or schemas/). Free-text evidence and
source-repository URLs are exempt, so a node may cite a vendor as evidence or
name its upstream repository without tripping the gate.

This wraps ci/taint_gate.py, the portable fail-closed detector, and runs it
over the registry root. It fails closed on any canonical-identity taint, which
keeps the neutrality guarantee on the write path (ELMM-I39): the whole gate is
CI, and neutrality is one of its checks.

Usage:
    python check_taint.py [--root <registry-root>]
"""

import argparse
import os
import subprocess
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(description="ELMM registry neutrality check")
    parser.add_argument("--root", default=None, help="registry root directory")
    args = parser.parse_args(argv)

    ci_dir = os.path.dirname(os.path.abspath(__file__))
    root = args.root or os.path.dirname(ci_dir)
    gate = os.path.join(ci_dir, "taint_gate.py")

    sys.stdout.write("check_taint: canonical-identity neutrality (open standard, no commercial coupling)\n")
    sys.stdout.write("  root: " + os.path.abspath(root) + "\n")
    sys.stdout.flush()

    proc = subprocess.run([sys.executable, gate, root])
    if proc.returncode == 0:
        sys.stdout.write("check_taint: PASS\n")
        return 0
    sys.stdout.write("check_taint: FAIL (canonical-identity taint found above)\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
