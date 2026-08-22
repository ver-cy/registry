#!/usr/bin/env bash
# Execute the idempotent Vercy catalogue migration as the web-server user so
# Bitrix can invalidate its managed caches after schema and content changes.
set -euo pipefail

HC_SSH_PASS="$(sed -n 's/^HC_SSH_PASS=//p' "$HOME/.hackathon-cy/secrets.env")"
[ -n "$HC_SSH_PASS" ] || { echo "HC_SSH_PASS not found" >&2; exit 3; }
case "$HC_SSH_PASS" in *\'*) echo "password contains a quote; adjust quoting" >&2; exit 3;; esac

ssh hcbox bash -s <<REMOTE
set -euo pipefail
HC_SSH_PASS='${HC_SSH_PASS}'
printf '%s\n' "\$HC_SSH_PASS" | sudo -S -p '' -u nginx php /data/web/www/ver.cy/tools/server/migrate-vercy-catalog.php
printf '%s\n' "\$HC_SSH_PASS" | sudo -S -p '' -u nginx python3 /data/web/www/ver.cy/tools/gen_sitemap.py
bash /data/web/www/ver.cy/tools/check_aeo.sh
REMOTE
