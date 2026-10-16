# Camilla's Notes

My public digital garden — PM, AI workflows, course and book notes — built with [Quartz v5](https://quartz.jzhao.xyz/) and deployed on Vercel.

## How it fits together

| Where | What |
|---|---|
| iCloud `Obsidian-Vault` | **The source of truth.** I only ever write notes here. |
| this repo (`~/Claude/camilla-notes`, local, *not* in iCloud) | The build factory: a filtered copy of the public notes + Quartz. |
| Vercel | Rebuilds and redeploys automatically on every push to `main`. |

## Publishing updates

```bash
./scripts/sync.sh            # rebuild content/ from the vault, show diff, ask before pushing
./scripts/sync.sh --dry-run  # rebuild and show diff only
```

`scripts/sync_from_vault.py` follows the publishing policy:

- **Allow-list only** — published folders: `2 Areas/{PM, AI 工作流、模版, 課程, 書, 認證、證照}` and `_Topics`. Anything else in the vault (new folders included) stays private.
- Attachments are copied only when a published note embeds them; **PDFs are never published**.
- `overrides/` holds site-only pages (the landing page `index.md`, folder indexes) and is layered on top.
- Dataview blocks are converted to static lists (`scripts/static_dataview.py`).
- A privacy guard aborts the sync if private folders, PDFs, or private contact info show up.

## Local preview

```bash
npx quartz build --serve   # http://localhost:8080
```

## Updating Quartz itself

The official repo is kept as the `upstream` remote:

```bash
git fetch upstream && git merge upstream/v5 --allow-unrelated-histories
```
