#!/usr/bin/env python3
"""check_conventions: the scaffold-convention admission check (S1, S2).

The seventh admission check. It gives the standard-scaffold backlog items their
acceptance tests without touching the ELMM kernel or any of the six existing
checks. Three conventions, each grounded in the Meta-Universe standard and each
failing closed with a precise diagnostic, but passing with an informative note
while the convention does not yet apply (so the scaffold can be built and shipped
incrementally, the same vacuous-pass discipline as check_instantiations):

  (a) ARTIFACT HEADER SCHEMA (S1). schema/artifact-header.schema.json, the
      reusable header carried by every artifact and Finding (id, title, status,
      change_history of {date, author, summary}, grounded in ARCH-002 versioning
      and IC-8 append-only), is a valid JSON Schema: the draft validator its
      $schema selects accepts it under check_schema. When the file is not yet
      committed the convention does not yet apply and the check passes with a
      note.

  (b) NO DATE IN FILENAME (S1). No file under entries/, mmdg/ or schema/ carries
      a date in its filename, where a date is the pattern \\d{4}-\\d{2}-\\d{2} or
      a bare \\d{8} run. Dates belong in the artifact header change_history, not
      in the name (a candidate ARCH-003 clause, filed as a change request, not
      edited into the published standard here). This convention always applies;
      the scan is recursive over the three directories.

  (c) CONVENTIONS DOCUMENTED. When conventions/README.md exists it is non-empty,
      so the scaffold conventions are actually written down where they are cited
      as Meta-Universe change requests. When it is absent the convention does not
      yet apply and the check passes with a note.

Exits non-zero with a precise message on the first violation. Follows the
existing "ok" line style. The root defaults to the parent of this script's
directory, so the check is working directory independent and reusable on a
copied tree.

Usage:
    python check_conventions.py [--root <registry-root>]
"""

import argparse
import os
import re
import sys

import _common as c


# Repo-relative locations, as path segment tuples so they join on any platform.
ARTIFACT_HEADER_SCHEMA = ("schema", "artifact-header.schema.json")
CONVENTIONS_README = ("conventions", "README.md")

# The three directories the no-date-in-filename rule (S1) governs.
DATED_FILENAME_DIRS = (("entries",), ("mmdg",), ("schema",))

# A date in a filename is either an ISO calendar date (YYYY-MM-DD) or a bare
# eight-digit compact date (YYYYMMDD). Both are forbidden by S1.
DATE_IN_FILENAME = re.compile(r"\d{4}-\d{2}-\d{2}|\d{8}")


def _abspath(root, segments):
    return os.path.join(root, *segments)


def _rel(segments):
    return "/".join(segments)


# ---------------------------------------------------------------------------
# (a) the artifact header schema is a valid JSON Schema
# ---------------------------------------------------------------------------

def _check_artifact_header_schema(root):
    path = _abspath(root, ARTIFACT_HEADER_SCHEMA)
    if not os.path.isfile(path):
        c.ok(
            _rel(ARTIFACT_HEADER_SCHEMA) + " is not committed yet; the S1 artifact"
            + " header convention does not yet apply (vacuously passes)"
        )
        return

    schema = c.load_json_file(path)
    if not isinstance(schema, dict):
        raise c.CheckError(
            _rel(ARTIFACT_HEADER_SCHEMA) + " is not a JSON object, so it is not a"
            + " JSON Schema document: " + path
        )

    from jsonschema.validators import validator_for

    validator_cls = validator_for(schema)
    try:
        validator_cls.check_schema(schema)
    except Exception as exc:
        raise c.CheckError(
            _rel(ARTIFACT_HEADER_SCHEMA) + " is not a valid JSON Schema (S1 artifact"
            + " header, id/title/status/change_history per ARCH-002 and IC-8): "
            + str(exc)
        )

    dialect = schema.get("$schema") or validator_cls.META_SCHEMA.get("$id", "the default draft")
    c.ok(
        "artifact header schema " + _rel(ARTIFACT_HEADER_SCHEMA)
        + " is a valid JSON Schema (dialect " + str(dialect) + ")"
    )


# ---------------------------------------------------------------------------
# (b) no date in any filename under entries/, mmdg/ or schema/
# ---------------------------------------------------------------------------

def _check_no_date_in_filenames(root):
    scanned = 0
    for segments in DATED_FILENAME_DIRS:
        directory = _abspath(root, segments)
        if not os.path.isdir(directory):
            # A missing governed directory is another check's concern; the naming
            # rule simply has nothing to scan there.
            continue
        for dirpath, _dirs, files in os.walk(directory):
            for name in sorted(files):
                scanned += 1
                match = DATE_IN_FILENAME.search(name)
                if match:
                    full = os.path.join(dirpath, name)
                    rel = os.path.relpath(full, root).replace(os.sep, "/")
                    raise c.CheckError(
                        "the filename " + rel + " carries a date pattern "
                        + repr(match.group(0)) + " (S1 no-date-in-filename rule,"
                        + " a candidate ARCH-003 clause); a date belongs in the"
                        + " artifact header change_history, never in the filename"
                    )
    c.ok(
        "no-date-in-filename: " + str(scanned) + " files under "
        + ", ".join(_rel(seg) + "/" for seg in DATED_FILENAME_DIRS)
        + " carry no date in their name"
    )


# ---------------------------------------------------------------------------
# (c) the conventions, when documented, are non-empty
# ---------------------------------------------------------------------------

def _check_conventions_documented(root):
    path = _abspath(root, CONVENTIONS_README)
    if not os.path.isfile(path):
        c.ok(
            _rel(CONVENTIONS_README) + " is not present yet; the documented-conventions"
            + " convention does not yet apply (vacuously passes)"
        )
        return
    try:
        with open(path, "r", encoding="utf-8") as handle:
            text = handle.read()
    except OSError as exc:
        raise c.CheckError("could not read " + _rel(CONVENTIONS_README) + " (" + path + "): " + str(exc))
    if not text.strip():
        raise c.CheckError(
            _rel(CONVENTIONS_README) + " exists but is empty; the scaffold conventions"
            + " (S1 header and no-date rule, S2 AGENTS.md, the /.vercy/ bundle) must be"
            + " documented where they are cited as Meta-Universe change requests"
        )
    c.ok(
        _rel(CONVENTIONS_README) + " documents the scaffold conventions ("
        + str(len(text)) + " chars)"
    )


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def run(root):
    c.info("check_conventions: scaffold-convention integrity (S1, S2)")
    c.info("  root: " + root)

    # (a) the S1 artifact header schema is a valid JSON Schema
    _check_artifact_header_schema(root)
    # (b) the S1 no-date-in-filename rule holds over the three governed directories
    _check_no_date_in_filenames(root)
    # (c) the scaffold conventions, when written down, are non-empty
    _check_conventions_documented(root)

    c.info("check_conventions: PASS")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Vercy registry scaffold-convention check")
    parser.add_argument("--root", default=None, help="registry root directory")
    args = parser.parse_args(argv)
    try:
        run(c.registry_root(args.root))
        return 0
    except c.CheckError as exc:
        sys.stderr.write("check_conventions: FAIL\n" + str(exc) + "\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
