#!/usr/bin/env python3
"""Rebuild content/ from the Obsidian vault, following the publishing policy.

Policy (from camilla-notes-prep/HANDOFF.md, plus later decisions):
  * Only the folders in PUBLIC are published (allow-list, never a deny-list,
    so new vault folders such as `2 Areas/AI PM` stay private by default).
  * Attachments are copied only when a published note embeds/links them.
  * No PDFs are published (iPAS exam papers and study guides were removed).
  * overrides/ holds site-only pages (landing page, folder indexes) and is
    layered on top, so a sync never wipes them.

The new tree is built in a staging dir, checked by a privacy guard, and only
then mirrored into content/. Nothing is committed here; see scripts/sync.sh.
"""
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date

REPO = pathlib.Path(__file__).resolve().parent.parent
VAULT = pathlib.Path(os.environ.get(
    "VAULT",
    pathlib.Path.home() / "Library/Mobile Documents/iCloud~md~obsidian/Documents/Obsidian-Vault",
))
PUBLIC = [
    "2 Areas/PM",
    "2 Areas/AI 工作流、模版",
    "2 Areas/課程",
    "2 Areas/書",
    "2 Areas/認證、證照",
    "_Topics",
]
SKIP_NAMES = {".DS_Store", ".obsidian"}
SKIP_SUFFIXES = {".pdf"}
# Anything matching these must never reach the published tree.
PRIVATE_SEGMENTS = {"0 Inbox", "1 Projects", "3 Resources", "4 Archive", "Daily Notes",
                    "_Templates", "_Bases", "Excalidraw", "AI PM"}
PRIVATE_FILES = {"RESUME.md", "PARA 懶人守則.md", "Home.md"}
PRIVATE_TEXT = re.compile(r"0922608482|sandy246836@hotmail")

EMBED = re.compile(r"!?\[\[([^\]|#]+)")
TEMPLATER = re.compile(r"<%[^%]*%>")


def die(msg):
    sys.exit(f"✋ sync aborted: {msg}")


def copy_public(stage):
    for rel in PUBLIC:
        src = VAULT / rel
        if not src.is_dir():
            die(f"missing public folder in vault: {rel}")
        for path in src.rglob("*"):
            if path.is_dir() or path.name in SKIP_NAMES or path.suffix.lower() in SKIP_SUFFIXES:
                continue
            if any(part in SKIP_NAMES for part in path.parts):
                continue
            dest = stage / path.relative_to(VAULT)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)


def copy_attachments(stage):
    names = set()
    for note in list(stage.rglob("*.md")) + list(stage.rglob("*.canvas")):
        for target in EMBED.findall(note.read_text(encoding="utf-8")):
            names.add(pathlib.Path(target.strip()).name)
    attach = VAULT / "Attachments"
    copied = 0
    for name in sorted(names):
        src = attach / name
        if src.is_file() and src.suffix.lower() not in SKIP_SUFFIXES:
            dest = stage / "Attachments" / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            copied += 1
    return copied


def fix_templater(stage):
    """Unrendered Templater tags (e.g. `created: <% tp.date.now() %>`)."""
    today = date.today().isoformat()
    for note in stage.rglob("*.md"):
        text = note.read_text(encoding="utf-8")
        if "<%" in text:
            updated = re.search(r"^updated:\s*(\d{4}-\d{2}-\d{2})", text, re.M)
            note.write_text(TEMPLATER.sub(updated.group(1) if updated else today, text), encoding="utf-8")
            print(f"  fixed Templater tag: {note.relative_to(stage)}")


def privacy_guard(stage):
    problems = []
    for path in stage.rglob("*"):
        rel = path.relative_to(stage)
        if set(rel.parts) & PRIVATE_SEGMENTS:
            problems.append(f"private folder: {rel}")
        if path.name in PRIVATE_FILES and rel.parent == pathlib.Path("."):
            problems.append(f"private file: {rel}")
        if path.suffix.lower() in SKIP_SUFFIXES:
            problems.append(f"pdf: {rel}")
        if path.suffix in {".md", ".canvas"} and PRIVATE_TEXT.search(path.read_text(encoding="utf-8")):
            problems.append(f"private contact info: {rel}")
    if problems:
        die("privacy guard failed:\n  " + "\n  ".join(problems[:20]))


def main():
    if not VAULT.is_dir():
        die(f"vault not found at {VAULT}")
    with tempfile.TemporaryDirectory(prefix="camilla-notes-") as tmp:
        stage = pathlib.Path(tmp) / "content"
        stage.mkdir()
        copy_public(stage)
        n_attach = copy_attachments(stage)
        shutil.copytree(REPO / "overrides", stage, dirs_exist_ok=True)
        fix_templater(stage)
        subprocess.run([sys.executable, str(REPO / "scripts/static_dataview.py"), str(stage)], check=True)
        privacy_guard(stage)
        n_md = len(list(stage.rglob("*.md")))
        # Mirror into content/ (deletes notes that were removed from the vault).
        subprocess.run(["rsync", "-a", "--delete", f"{stage}/", f"{REPO / 'content'}/"], check=True)
    print(f"✅ content/ rebuilt: {n_md} notes, {n_attach} attachments")


if __name__ == "__main__":
    main()
