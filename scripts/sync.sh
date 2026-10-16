#!/usr/bin/env bash
# One-command publish: Obsidian vault (iCloud) -> content/ -> GitHub -> Vercel.
#
#   ./scripts/sync.sh            rebuild content/, show the diff, ask before pushing
#   ./scripts/sync.sh --dry-run  rebuild content/ and show the diff only
#
# Vercel redeploys automatically on every push to main.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "① Rebuilding content/ from the vault (public folders only)…"
python3 scripts/sync_from_vault.py

echo
echo "② Changes:"
git add -A content
if git diff --cached --quiet -- content; then
  echo "   No changes — the site is already up to date."
  exit 0
fi
git diff --cached --stat -- content | tail -15

if [[ "${1:-}" == "--dry-run" ]]; then
  git reset -q -- content
  echo; echo "Dry run: content/ updated locally, nothing committed."
  exit 0
fi

echo
read -r -p "③ Publish these changes to the website? [y/N] " answer
if [[ "$answer" != [yY] ]]; then
  git reset -q -- content
  echo "Not published. (content/ is updated locally; run again when ready.)"
  exit 0
fi

git commit -q -m "Sync notes from vault ($(date +%Y-%m-%d))"
git push -q origin main
echo "✅ Pushed. Vercel will redeploy in about a minute."
