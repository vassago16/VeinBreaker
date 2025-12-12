import json
import shutil
from pathlib import Path


def ability_card(ab):
    name = ab.get("name", "Unnamed")
    path = ab.get("path", "unknown").title()
    typ = ab.get("type", "")
    cost = ab.get("cost", "?")
    cd = ab.get("cooldown", "")
    cd_str = "—" if cd is None else cd
    effect = ab.get("effect", "").strip()
    tags = ", ".join(ab.get("tags", []))
    lines = [
        f"**{name}** ({path} - {typ})",
        f"Cost: {cost} RP; CD: {cd_str}",
        f"{effect}",
    ]
    if tags:
        lines.append(f"_Tags: {tags}_")
    return "<br>".join(lines)


def chunk(seq, size):
    return [seq[i : i + size] for i in range(0, len(seq), size)]


def main():
    root = Path(__file__).parent
    data = json.loads((root / "abilities.json").read_text(encoding="utf-8"))
    abilities = data.get("abilities", [])

    # group by tier
    by_tier = {}
    for ab in abilities:
        by_tier.setdefault(ab.get("tier", 0), []).append(ab)

    out_dir = root / "build"
    out_dir.mkdir(parents=True, exist_ok=True)
    generated = []

    for tier in sorted(by_tier):
        group = sorted(by_tier[tier], key=lambda a: (a.get("path", ""), a.get("name", "")))
        cards = [ability_card(ab) for ab in group]
        rows = chunk(cards, 3)

        lines = [
            f"# Tier {tier} Abilities",
            "",
            "|  |  |  |",
            "| --- | --- | --- |",
        ]
        for row in rows:
            # pad row to 3 columns
            while len(row) < 3:
                row.append("")
            lines.append("| " + " | ".join(row) + " |")

        path = out_dir / f"tier-{tier}-abilities.md"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        generated.append(path)

    # copy to wiki if present
    wiki_dir = root.parent / "docs" / "wiki"
    if wiki_dir.exists():
        wiki_dir.mkdir(parents=True, exist_ok=True)
        for src in generated:
            shutil.copy(src, wiki_dir / src.name)


if __name__ == "__main__":
    main()
