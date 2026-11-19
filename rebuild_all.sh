#!/bin/sh
set -e
cd "$(dirname "$0")"
../.venv/bin/pip install -q beautifulsoup4==4.15.0
echo "=== scrape ==="
../.venv/bin/python scrape.py
echo "=== enrich ==="
../.venv/bin/python enrich.py
echo "=== prune ==="
../.venv/bin/python fix_and_prune.py
echo "=== focus ==="
../.venv/bin/python focus.py
echo "=== add missing schedule-only subjects ==="
../.venv/bin/python add_missing.py
echo "=== build ==="
../.venv/bin/python build.py
echo "=== verify ==="
../.venv/bin/python verify.py
echo "=== link sample ==="
if [ "${SKIP_LINK_SAMPLE:-0}" = "1" ]; then
  echo "link sample skipped (SKIP_LINK_SAMPLE=1)"
else
  ../.venv/bin/python test_links.py
fi
echo "=== UI smoke test ==="
if [ "${SKIP_UI:-0}" != "1" ]; then
  JSDOM_VERSION=$(node -p "require('./package.json').devDependencies.jsdom")
  if ! node -e "process.exit(require('jsdom/package.json').version === '$JSDOM_VERSION' ? 0 : 1)" >/dev/null 2>&1; then
    echo "Installing locked UI test dependencies (npm ci)..."
    npm ci
  fi
  REQUIRE_UI=1 node verify_ui.js
else
  echo "UI smoke test skipped (SKIP_UI=1)"
fi
echo "=== DONE ==="
