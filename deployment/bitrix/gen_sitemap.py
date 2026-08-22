#!/usr/bin/env python3
"""Regenerate sitemap.xml for ver.cy. Run after adding pages or documents:
   sudo python3 /data/web/www/ver.cy/tools/gen_sitemap.py
Picks up every *.md under */docs plus known HTML sections automatically."""
import json
import os
import time
import html

ROOT = "/data/web/www/ver.cy"
BASE = "https://ver.cy"

# HTML sections: any directory at depth 1 holding an index.html
def html_sections():
    out = [("/", "1.0")]
    for name in sorted(os.listdir(ROOT)):
        d = os.path.join(ROOT, name)
        if name in ("log", "assets", "schemas") or not os.path.isdir(d):
            continue
        if os.path.isfile(os.path.join(d, "index.html")):
            prio = "0.9" if name in ("spec", "models", "processes") else "0.8"
            out.append(("/%s/" % name, prio))
    if os.path.isfile(os.path.join(ROOT, "schemas", "index.html")):
        out.append(("/schemas/", "0.6"))
    models_root = os.path.join(ROOT, "models")
    for name in sorted(os.listdir(models_root)):
        d = os.path.join(models_root, name)
        if os.path.isdir(d) and os.path.isfile(os.path.join(d, "index.html")):
            out.append(("/models/%s/" % name, "0.8"))
    return out


def registry_models():
    """Include Bitrix-routed catalogue pages, including planned TODO entries."""
    source = os.path.join(ROOT, "tools", "server", "vercy-catalog-import.json")
    try:
        with open(source, encoding="utf-8") as stream:
            payload = json.load(stream)
    except (OSError, ValueError):
        return []
    generated = str(payload.get("generated_at", ""))[:10] or time.strftime("%Y-%m-%d", time.gmtime())
    return [
        (model["page_url"], generated, "0.8" if model.get("spec_available") else "0.6")
        for model in payload.get("models", [])
        if model.get("page_url", "").startswith("/models/")
    ]

machine = ["/llms.txt", "/AGENTS.md", "/spec-index.yaml",
           "/external-models.csv", "/composition-connectors.csv",
           "/models/world-models.csv", "/processes/processes.csv"]

def lastmod(rel):
    p = os.path.join(ROOT, rel.lstrip("/"))
    if os.path.isdir(p):
        p = os.path.join(p, "index.html")
    try:
        return time.strftime("%Y-%m-%d", time.gmtime(os.path.getmtime(p)))
    except OSError:
        return time.strftime("%Y-%m-%d", time.gmtime())

entries = [(u, lastmod(u), p) for u, p in html_sections()]
entries.extend(registry_models())
for u in machine:
    if os.path.isfile(os.path.join(ROOT, u.lstrip("/"))):
        entries.append((u, lastmod(u), "0.5"))

docs = 0
for dirpath, _d, files in os.walk(ROOT):
    if os.sep + "docs" not in dirpath:
        continue
    for fn in sorted(files):
        if fn.endswith(".md"):
            rel = "/" + os.path.relpath(os.path.join(dirpath, fn), ROOT).replace(os.sep, "/")
            entries.append((rel, lastmod(rel), "0.7"))
            docs += 1

deduplicated = {}
for url, modified, priority in entries:
    previous = deduplicated.get(url)
    if previous is None or float(priority) > float(previous[1]):
        deduplicated[url] = (modified, priority)
entries = [(url, *values) for url, values in deduplicated.items()]

out = ['<?xml version="1.0" encoding="UTF-8"?>',
       '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
for u, m, pr in entries:
    out += ["  <url>", "    <loc>%s%s</loc>" % (BASE, html.escape(u)),
            "    <lastmod>%s</lastmod>" % m, "    <priority>%s</priority>" % pr, "  </url>"]
out.append("</urlset>")
open(os.path.join(ROOT, "sitemap.xml"), "w", encoding="utf-8").write("\n".join(out) + "\n")
print("sitemap.xml: %d urls (%d documents, %d registry models)" % (len(entries), docs, len(registry_models())))
