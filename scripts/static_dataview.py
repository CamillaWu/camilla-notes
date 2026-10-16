#!/usr/bin/env python3
"""Replace Obsidian Dataview blocks with static Markdown lists.

Quartz cannot run Dataview, so each query in the five index/topic pages is
evaluated here against the *published* notes only (so nothing private can
leak into a list) and swapped for a plain list. Safe to re-run after every
vault sync: pages are rebuilt from the dataview source each time.

Usage:  python3 scripts/static_dataview.py   (run from the repo root)
"""
import pathlib
import re

CONTENT = pathlib.Path("content")
BLOCK = re.compile(r"```dataview\n.*?\n```", re.S)
WIKILINK = re.compile(r"\[\[([^\]|#]+)")


def frontmatter(text):
    if not text.startswith("---\n"):
        return ""
    end = text.find("\n---", 4)
    return text[4:end] if end != -1 else ""


def topics(text):
    """Topic values from frontmatter (list or inline) and `Topic::` fields."""
    fm = frontmatter(text)
    found, in_topic = [], False
    for line in fm.splitlines():
        if re.match(r"^Topic:", line):
            in_topic = True
            found += WIKILINK.findall(line)
            continue
        if in_topic and re.match(r"^\s+-\s", line):
            found += WIKILINK.findall(line)
        else:
            in_topic = False
    for line in text.splitlines():
        if line.startswith("Topic::"):
            found += WIKILINK.findall(line)
    return [t.strip() for t in found if t.strip()]


def notes(folder):
    base = CONTENT / folder
    return sorted(
        (p for p in base.rglob("*.md") if p.name != "_index.md"),
        key=lambda p: str(p.relative_to(base)),
    )


def link(p, in_table=False):
    rel = p.relative_to(CONTENT).with_suffix("")
    sep = "\\|" if in_table else "|"  # a bare | would split a table cell
    return f"[[{rel}{sep}{p.stem}]]"


def subfolder(p, folder):
    parent = p.parent.relative_to(CONTENT / folder)
    return "" if str(parent) == "." else str(parent)


ALL = {p: topics(p.read_text(encoding="utf-8")) for p in CONTENT.rglob("*.md")}
TOPIC_PAGES = notes("_Topics")
TOPIC_NAMES = {p.stem for p in TOPIC_PAGES}


def cards_for(topic):
    return sorted(
        (p for p, ts in ALL.items() if topic in ts and p.parent != CONTENT / "_Topics"),
        key=lambda p: str(p),
    )


def as_list(paths, folder_label=False):
    if not paths:
        return "_（目前沒有）_"
    out = []
    for p in paths:
        extra = ""
        if folder_label:
            extra = f" — {p.parent.relative_to(CONTENT)}"
        out.append(f"- {link(p)}{extra}")
    return "\n".join(out)


def pm_index(text):
    pm = notes("2 Areas/PM")
    blocks = [
        as_list(pm),
        as_list([p for p in pm if not ALL[p]]),
        None,  # private 3 Resources/PDFs query -> drop the whole section
    ]
    text = text.replace("## 🃏 PM 所有卡片（最近修改）", "## 🃏 PM 所有卡片")
    text = fill(text, blocks)
    return re.sub(r"\n## 📎 相關 PDF\n+\s*", "\n", text).rstrip() + "\n"


def ai_index(text):
    folder = "2 Areas/AI 工作流、模版"
    items = []
    for p in notes(folder):
        sub = subfolder(p, folder)
        items.append(f"- {link(p)}" + (f" — {sub}" if sub else ""))
    return fill(text, ["\n".join(items)])


def topics_index(text):
    rows = ["| Topic | 被連卡片數 |", "| --- | --- |"]
    counts = sorted(((len(cards_for(p.stem)), p) for p in TOPIC_PAGES), key=lambda x: (-x[0], x[1].stem))
    rows += [f"| {link(p, True)} | {n} |" for n, p in counts]
    orphans = [p for n, p in counts if n == 0]
    used = {}
    for p, ts in ALL.items():
        for t in ts:
            if t not in TOPIC_NAMES and p.parent != CONTENT / "_Topics":
                used.setdefault(t, []).append(p)
    missing = ["| Topic | 次數 | 在哪幾張卡用到 |", "| --- | --- | --- |"]
    for t, ps in sorted(used.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        cards = "、".join(link(p, True) for p in sorted(ps, key=str))
        missing.append(f"| {t} | {len(ps)} | {cards} |")
    return fill(text, ["\n".join(rows), as_list(orphans), "\n".join(missing)])


def topic_page(text, path):
    text = fill(text, [as_list(cards_for(path.stem), folder_label=True), None])
    # "last 30 days" can't stay accurate on a static site, and the
    # connections block only held empty `= this.parent`-style queries.
    text = re.sub(r"\n## 📅 最近 30 天有更新的相關卡片\n+\s*(?=\n## )", "\n", text)
    text = re.sub(r"\n## 🔗 關聯主題 \(Connections\)\n+(?:- .*`= this\.[a-z]+`\n)+", "\n", text)
    return text


def fill(text, replacements):
    blocks = BLOCK.findall(text)
    assert len(blocks) == len(replacements), (len(blocks), len(replacements))
    for block, new in zip(blocks, replacements):
        text = text.replace(block, "" if new is None else new, 1)
    return text


def ensure_titles():
    """Folder pages are named `_index`; give them a readable title from their H1."""
    for p in CONTENT.rglob("_index.md"):
        t = p.read_text(encoding="utf-8")
        fm = frontmatter(t)
        if re.search(r"^title:", fm, re.M):
            continue
        h1 = re.search(r"^# (.+)$", t, re.M)
        if not h1:
            continue
        title = h1.group(1).strip().replace('"', "'")
        if t.startswith("---\n"):
            t = t.replace("---\n", f'---\ntitle: "{title}"\n', 1)
        else:
            t = f'---\ntitle: "{title}"\n---\n' + t
        p.write_text(t, encoding="utf-8")
        print("titled:", p.relative_to(CONTENT), "->", title)


FIELD = re.compile(r"^(parent|child|sibling):: *(.*)$")


def clean_metadata():
    """Drop empty Obsidian template fields (`parent:: [[]]`) that render as noise.

    Fields with real links are kept; a `### Metadata` heading left with no
    fields under it is removed too.
    """
    changed = 0
    for p in CONTENT.rglob("*.md"):
        lines = p.read_text(encoding="utf-8").split("\n")
        out = []
        for line in lines:
            m = FIELD.match(line)
            if m:
                value = re.sub(r"\[\[\]\]", "", m.group(2)).strip(" ,")
                if not value:
                    continue
                line = f"{m.group(1)}:: {value}"
            out.append(line)
        cleaned = []
        for i, line in enumerate(out):
            if line.strip() == "### Metadata":
                rest = next((l for l in out[i + 1:] if l.strip()), "")
                if not FIELD.match(rest):
                    continue
            cleaned.append(line)
        new = "\n".join(cleaned)
        if new != "\n".join(lines):
            p.write_text(new, encoding="utf-8")
            changed += 1
    print(f"cleaned metadata in {changed} files")


def main():
    clean_metadata()
    ensure_titles()
    jobs = {
        "2 Areas/PM/_index.md": pm_index,
        "2 Areas/AI 工作流、模版/_index.md": ai_index,
        "_Topics/_index.md": topics_index,
    }
    for rel, fn in jobs.items():
        p = CONTENT / rel
        t = p.read_text(encoding="utf-8")
        if "```dataview" in t:
            p.write_text(fn(t), encoding="utf-8")
            print("static:", rel)
    for p in TOPIC_PAGES:
        t = p.read_text(encoding="utf-8")
        if "```dataview" in t:
            p.write_text(topic_page(t, p), encoding="utf-8")
            print("static:", p.relative_to(CONTENT))


if __name__ == "__main__":
    main()
