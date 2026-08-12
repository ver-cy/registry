#!/usr/bin/env python3
"""taint_gate.py - portable CI gate for the ver.cy open standard.

ver.cy is an OPEN STANDARD that must carry ZERO commercial coupling. This gate
walks a target tree and FAILS CLOSED (exit 1) if any forbidden token appears in
a CANONICAL-IDENTITY position. Forbidden tokens are the vendor/product names of
the standard's own toolchain and of named commercial ERP/PLM/EAM suites:

    orkestron, orkestro, aeilus, amsi,
    sap, oracle, dynamics, salesforce, servicenow,
    workday, maximo, teamcenter, opentext, celonis

CANONICAL-IDENTITY positions checked:
  - schema $id and title values (JSON Schema draft 2020-12 files);
  - values of YAML/JSON keys named: csn, namespace (any *namespace, e.g.
    primary_namespace), id, model_id, display_alias - these carry layer,
    object and relation identity;
  - file and directory names under any registry/ or schemas/ path segment.

Those same tokens are ALLOWED where they are explicitly marked as free-text
evidence (a source's real product name is legitimate evidence, never identity):
  - any path containing /evidence/, evidence-source-map, /BS7/, /top10-it/,
    or /standards-reviews/;
  - any value nested under a key literally named 'evidence' or 'source'.

Each violation prints as  path:line:token  (line 0 means a file/dir name).
Dependency-free stdlib only; Windows- and POSIX-safe.

Usage:
    python taint_gate.py [TARGET_DIR]     # default TARGET_DIR = current dir
    python taint_gate.py --self-test      # in-memory detector self check
"""

import os
import re
import sys

FORBIDDEN = (
    "orkestron", "orkestro", "aeilus", "amsi",
    "sap", "oracle", "dynamics", "salesforce", "servicenow",
    "workday", "maximo", "teamcenter", "opentext", "celonis",
)

# Left-boundary guard only (no right guard) so we fail closed: superstrings such
# as 'oracledb' or 'sapui5' still trip the gate. The left guard stops mid-word
# hits like the 'sap' inside 'landscape' (there is none) or 'disappoint'.
_TOKEN_RE = {
    tok: re.compile(r"(?<![A-Za-z0-9])" + re.escape(tok), re.IGNORECASE)
    for tok in FORBIDDEN
}

# Canonical-identity keys. '$id' and 'title' are schema identity; the rest are
# registry/record identity. The '[A-Za-z_]*namespace' alternative catches both
# bare 'namespace' and compounds like 'primary_namespace'.
_KEY_RE = re.compile(
    r"""^\s*["']?
        (\$id|title|csn|model_id|display_alias|[A-Za-z_]*namespace|id)
        ["']?\s*:\s*(.+?)\s*$""",
    re.VERBOSE,
)

# A mapping key literally named 'evidence' or 'source' opens an allowed block:
# everything more-indented beneath it is free-text evidence.
_EVIDENCE_KEY_RE = re.compile(
    r"""^(\s*)["']?(evidence|source)["']?\s*:\s*(.*)$""",
    re.IGNORECASE,
)

# Whole-file evidence locations: if any of these appears in the (slash-normalized,
# lowercased) path, the file is evidence and is skipped entirely.
_EVIDENCE_PATH_MARKERS = (
    "/evidence/", "evidence-source-map",
    "/bs7/", "/top10-it/", "/standards-reviews/",
)

_CANONICAL_NAME_ROOTS = ("registry", "schemas")
_SKIP_DIRS = {".git", ".hg", ".svn", "node_modules", "__pycache__", ".venv", "venv"}


def _find_tokens(value):
    """Return the forbidden tokens present in `value`, longest-match wins.

    'orkestron.aismm' yields ['orkestron', 'aismm'] - the shorter 'orkestro'
    is dropped because its match span is contained in 'orkestron'.
    """
    spans = []  # (start, end, token)
    for tok, rx in _TOKEN_RE.items():
        for m in rx.finditer(value):
            spans.append((m.start(), m.end(), tok))
    keep = []
    for s, e, tok in spans:
        contained = any(
            (os, oe, ot) != (s, e, tok) and os <= s and e <= oe and (oe - os) > (e - s)
            for (os, oe, ot) in spans
        )
        if not contained:
            keep.append((s, tok))
    # Deterministic order: by position, then token.
    seen = set()
    out = []
    for _, tok in sorted(keep):
        if tok not in seen:
            seen.add(tok)
            out.append(tok)
    return out


def _is_evidence_path(norm_path):
    p = norm_path.lower()
    return any(marker in p for marker in _EVIDENCE_PATH_MARKERS)


def scan_names(norm_relpath):
    """Flag forbidden tokens in file/dir names under a registry/ or schemas/ root.

    Every path segment AFTER a 'registry' or 'schemas' segment is canonical
    identity. Returns a list of (segment, token).
    """
    if _is_evidence_path(norm_relpath):
        return []
    parts = [p for p in norm_relpath.split("/") if p]
    out = []
    active = False
    for seg in parts:
        if active:
            for tok in _find_tokens(seg):
                out.append((seg, tok))
        if seg.lower() in _CANONICAL_NAME_ROOTS:
            active = True
    return out


def scan_text(norm_path, text):
    """Flag forbidden tokens in canonical-identity value positions in `text`.

    Returns a list of (line_number, token). Line numbers are 1-indexed.
    """
    if _is_evidence_path(norm_path):
        return []
    out = []
    # Stack of indentation levels under an open 'evidence'/'source' block.
    suppress_stack = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.rstrip("\n")
        if line.strip() == "":
            continue  # blank lines never open, close, or trip anything
        indent = len(line) - len(line.lstrip(" \t"))

        # Exit any evidence blocks we have dedented out of.
        while suppress_stack and indent <= suppress_stack[-1]:
            suppress_stack.pop()

        ev = _EVIDENCE_KEY_RE.match(line)
        if ev:
            inline = ev.group(3).strip()
            # An empty value, a block scalar, or a container opener starts a
            # multi-line evidence block; an inline scalar is self-contained.
            if inline == "" or inline in ("|", ">", "[", "{") or inline.startswith(("|", ">")):
                suppress_stack.append(indent)
            # Either way the evidence/source line itself is allowed.
            continue

        if suppress_stack:
            continue  # inside an allowed evidence/source block

        m = _KEY_RE.match(line)
        if not m:
            continue
        value = m.group(2).strip().strip('"').strip("'").strip()
        for tok in _find_tokens(value):
            out.append((lineno, tok))
    return out


def _read_text(path):
    try:
        with open(path, "rb") as fh:
            blob = fh.read()
    except OSError:
        return None
    if b"\x00" in blob:  # binary
        return None
    try:
        return blob.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return blob.decode("latin-1")
        except UnicodeDecodeError:
            return None


def walk(target):
    """Yield violation strings 'path:line:token' for the whole tree."""
    target = os.path.abspath(target)
    violations = []
    for root, dirs, files in os.walk(target):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
        for name in files:
            full = os.path.join(root, name)
            rel = os.path.relpath(full, target).replace("\\", "/")
            norm = full.replace("\\", "/")

            for seg, tok in scan_names(rel):
                violations.append("{0}:0:{1}".format(norm, tok))

            text = _read_text(full)
            if text is None:
                continue
            for lineno, tok in scan_text(norm, text):
                violations.append("{0}:{1}:{2}".format(norm, lineno, tok))
    return violations


def self_test():
    """Construct one clean and one tainted in-memory sample; assert the
    detector flags exactly the tainted one. Exit 0 on pass, 1 on fail."""
    clean = "\n".join([
        '{',
        '  "$schema": "https://json-schema.org/draft/2020-12/schema",',
        '  "$id": "https://ver.cy/schemas/core-record.schema.json",',
        '  "title": "Core Registration Record",',
        '  "csn": "software-meta-model",',
        '  "primary_namespace": "aismm-core",',
        '  "id": "vercy.elmm",',
        '  "model_id": "open-string-key",',
        '  "display_alias": "ELMM",',
        '  "source": {',
        '    "repository": "https://github.com/example/oracle-connector",',
        '    "product": "Oracle E-Business Suite"',
        '  },',
        '  "evidence": [',
        '    "seen in SAP S/4HANA and Salesforce deployments"',
        '  ]',
        '}',
    ])
    tainted = "\n".join([
        '{',
        '  "$id": "https://ver.cy/schemas/salesforce-record.schema.json",',
        '  "title": "ServiceNow Landscape",',
        '  "csn": "orkestron-thing",',
        '  "primary_namespace": "sap-erp",',
        '  "id": "orkestron.aismm",',
        '  "display_alias": "AMSI"',
        '}',
    ])

    clean_v = scan_text("mem/clean/core-record.schema.json", clean)
    tainted_v = scan_text("mem/tainted/record.schema.json", tainted)

    # Name-level check: a tainted filename under schemas/ must trip; a clean one
    # (and any evidence-path filename) must not.
    name_clean = scan_names("schemas/core-record.schema.json")
    name_tainted = scan_names("schemas/oracle-record.schema.json")
    # Under the schemas/ root (would flag 'oracle') but inside /evidence/, so
    # the evidence-path suppression must win.
    name_evidence = scan_names("schemas/evidence/oracle-record.schema.json")

    ok = True
    if clean_v:
        ok = False
        print("SELF-TEST FAIL: clean content flagged: {0}".format(clean_v))
    if not tainted_v:
        ok = False
        print("SELF-TEST FAIL: tainted content not flagged")
    if name_clean:
        ok = False
        print("SELF-TEST FAIL: clean name flagged: {0}".format(name_clean))
    if not name_tainted:
        ok = False
        print("SELF-TEST FAIL: tainted name not flagged")
    if name_evidence:
        ok = False
        print("SELF-TEST FAIL: evidence-path name flagged: {0}".format(name_evidence))

    tainted_tokens = sorted({t for _, t in tainted_v})
    expected = {"salesforce", "servicenow", "orkestron", "sap", "amsi"}
    if not expected.issubset(set(tainted_tokens)):
        ok = False
        print("SELF-TEST FAIL: expected tokens {0} not all found in {1}".format(
            sorted(expected), tainted_tokens))

    if ok:
        print("SELF-TEST PASS: detector flags exactly the tainted sample")
        print("  tainted content tokens: {0}".format(tainted_tokens))
        return 0
    return 1


def main(argv):
    if "--self-test" in argv:
        return self_test()
    target = argv[1] if len(argv) > 1 else "."
    if not os.path.isdir(target):
        print("taint_gate: target is not a directory: {0}".format(target), file=sys.stderr)
        return 1
    try:
        violations = walk(target)
    except Exception as exc:  # fail closed on any internal error
        print("taint_gate: internal error, failing closed: {0}".format(exc), file=sys.stderr)
        return 1
    if violations:
        for v in sorted(set(violations)):
            print(v)
        print("taint_gate: FAIL - {0} canonical-identity taint violation(s)".format(
            len(set(violations))), file=sys.stderr)
        return 1
    print("taint_gate: PASS - no canonical-identity taint found")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
