import json
import shutil
from pathlib import Path


def card(item):
    name = item.get("name", "Unnamed")
    tier = item.get("tier", "?")
    typ = item.get("type", "unknown").title()
    rarity = item.get("rarity", "")
    tags = ", ".join(item.get("tags", []))
    desc = item.get("description", "")
    lines = [
        f"**{name}** ({typ} / {rarity})",
        f"Tier {tier}",
        desc
    ]
    if tags:
        lines.append(f"_Tags: {tags}_")
    return "<br>".join(lines)


def chunk(seq, n):
    return [seq[i : i + n] for i in range(0, len(seq), n)]


def write_table(title, items, path, cols=3):
    cards = [card(i) for i in items]
    rows = chunk(cards, cols)
    lines = [
        f"# {title}",
        "",
        "| " + " | ".join([""] * cols) + " |",
        "| " + " | ".join(["---"] * cols) + " |",
    ]
    for row in rows:
        while len(row) < cols:
            row.append("")
        lines.append("| " + " | ".join(row) + " |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    root = Path(__file__).parent
    data = json.loads((root / "loot.json").read_text(encoding="utf-8"))
    loot = data.get("loot", [])

    out_dir = root / "loot-out"
    out_dir.mkdir(parents=True, exist_ok=True)
    generated = []

    # by tier
    by_tier = {}
    for itm in loot:
        by_tier.setdefault(itm.get("tier", "?"), []).append(itm)
    for tier, items in sorted(by_tier.items(), key=lambda kv: kv[0]):
        path = out_dir / f"loot-tier-{tier}.md"
        write_table(f"Loot Tier {tier}", sorted(items, key=lambda i: i.get("name", "")), path)
        generated.append(path)

    # by type
    by_type = {}
    for itm in loot:
        by_type.setdefault(itm.get("type", "unknown"), []).append(itm)
    for typ, items in sorted(by_type.items(), key=lambda kv: kv[0]):
        path = out_dir / f"loot-type-{typ}.md"
        title = f"Loot Type: {typ.title()}"
        write_table(title, sorted(items, key=lambda i: i.get("name", "")), path)
        generated.append(path)

    # copy to wiki if present
    wiki_dir = root.parent / "docs" / "wiki"
    if wiki_dir.exists():
        wiki_dir.mkdir(parents=True, exist_ok=True)
        for src in generated:
            shutil.copy(src, wiki_dir / src.name)


if __name__ == "__main__":
    main()
