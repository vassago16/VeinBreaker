import json
import copy
import shutil
from pathlib import Path


def deep_merge(base, override):
    if isinstance(base, dict) and isinstance(override, dict):
        merged = dict(base)
        for k, v in override.items():
            merged[k] = deep_merge(base.get(k), v)
        return merged
    return copy.deepcopy(override if override is not None else base)


def render_enemy_md(enemy, archetype_lookup):
    # helpers for rendering
    def format_damage(dmg_ref, stat_block):
        if not dmg_ref:
            return "n/a"
        dmg_prof = stat_block.get("damage_profile", {})
        if isinstance(dmg_ref, str) and dmg_ref in dmg_prof:
            ref = dmg_prof[dmg_ref]
            dice = ref.get("dice", "?")
            flat = ref.get("flat")
            flat_str = f"{flat:+}" if isinstance(flat, (int, float)) else ""
            return f"{dice}{flat_str} ({dmg_ref})"
        return str(dmg_ref)

    def prettify_ref(ref, move_lookup):
        if ref in move_lookup:
            return move_lookup[ref]
        if isinstance(ref, str) and ref.startswith("move."):
            ref = ref.split(".", 1)[1]
        return ref.replace("_", " ").title()

    def format_condition(cond: dict):
        parts = []
        for k, v in cond.items():
            label = k.replace("_", " ")
            if isinstance(v, bool):
                val = "yes" if v else "no"
            else:
                val = str(v)
            parts.append(f"{label}={val}")
        return ", ".join(parts)

    def format_behavior_steps(steps, move_lookup):
        rendered = []
        for step in steps:
            stype = step.get("type")
            if stype == "move":
                ref = step.get("ref", "")
                rendered.append(prettify_ref(ref, move_lookup))
            elif stype == "conditional":
                cond = format_condition(step.get("if", {}))
                then_steps = format_behavior_steps(step.get("then", []), move_lookup)
                then_text = "; then ".join(then_steps) if then_steps else "then act"
                rendered.append(f"If {cond}, {then_text}")
            else:
                rendered.append(str(step))
        return rendered

    name = enemy.get("name", enemy.get("id", "Unknown"))
    eid = enemy.get("id", "unknown")
    archetype_id = enemy.get("archetype_id")
    archetype_name = archetype_lookup.get(archetype_id, {}).get("name", archetype_id or "Unknown")
    tier = enemy.get("tier", "?")
    role = enemy.get("role", "")
    rarity = enemy.get("rarity", "")
    tags = ", ".join(enemy.get("tags", []))

    stats = enemy.get("stat_block", {})
    hp = stats.get("hp", {}).get("max", "?")
    defense = stats.get("defense", {})
    dv_base = defense.get("dv_base", "?")
    idf = defense.get("idf", 0)
    dmg = stats.get("damage_profile", {})
    baseline = dmg.get("baseline", {})
    spike = dmg.get("spike", {})

    lines = []
    lines.append(f"# {name}")
    lines.append("")
    lines.append(f"- **ID:** `{eid}`")
    lines.append(f"- **Archetype:** {archetype_name} (`{archetype_id}`)")
    lines.append(f"- **Tier/Role/Rarity:** {tier} / {role} / {rarity}")
    if tags:
        lines.append(f"- **Tags:** {tags}")
    lines.append(f"- **HP:** {hp}")
    lines.append(f"- **Defense:** DV {dv_base}, IDF {idf}")
    if baseline or spike:
        base_str = f"{baseline.get('dice','?')} {baseline.get('flat','')}".strip()
        spike_str = f"{spike.get('dice','?')} {spike.get('flat','')}".strip()
        lines.append(f"- **Damage:** baseline {base_str}, spike {spike_str}")

    lore = enemy.get("lore", {})
    if lore:
        lines.append("")
        lines.append("## Lore")
        if lore.get("one_liner"):
            lines.append(f"- {lore['one_liner']}")
        if lore.get("dungeon_voice"):
            lines.append(f"- Dungeon voice: {lore['dungeon_voice']}")
        if lore.get("notes_gm"):
            lines.append(f"- GM notes: {lore['notes_gm']}")

    moves = enemy.get("moves", [])
    move_lookup = {m.get("id"): m.get("name", m.get("id", "")) for m in moves}
    if moves:
        lines.append("")
        lines.append("## Moves")
        for mv in moves:
            mv_name = mv.get("name", mv.get("id", "Unnamed"))
            mv_type = mv.get("type", "")
            cost = mv.get("cost", {})
            rp_cost = cost.get("rp")
            cd = mv.get("cooldown", 0)
            on_hit = mv.get("on_hit", {})
            dmg_ref = on_hit.get("damage", "")
            effects = on_hit.get("effects", [])
            on_miss = mv.get("on_miss", {})
            card_text = mv.get("card_text", "")
            dmg_str = format_damage(dmg_ref, stats)
            eff_render = []
            for eff in effects:
                if isinstance(eff, str):
                    eff_render.append(eff)
                else:
                    eff_render.append(json.dumps(eff))
            effects_str = ", ".join(eff_render) if eff_render else "none"
            lines.append(f"- **{mv_name}** ({mv_type}) - RP {rp_cost}, CD {cd}, dmg: {dmg_str}, effects: {effects_str}")
            if on_miss.get("notes"):
                lines.append(f"  - On miss: {on_miss.get('notes')}")
            if card_text:
                lines.append(f"  - Text: {card_text}")

    resolved = enemy.get("resolved_archetype", {})
    ai = resolved.get("ai", {}).get("behavior_script", {})
    if ai:
        lines.append("")
        lines.append("## Behavior (Archetype)")
        opening = ai.get("opening", [])
        default_loop = ai.get("default_loop", [])
        if opening:
            rendered = format_behavior_steps(opening, move_lookup)
            lines.append(f"- Opening: {', '.join(rendered)}")
        if default_loop:
            rendered = format_behavior_steps(default_loop, move_lookup)
            lines.append(f"- Default loop: {', '.join(rendered)}")

    return "\n".join(lines) + "\n"


def render_enemy_card(enemy):
    name = enemy.get("name", enemy.get("id", "Unknown"))
    tier = enemy.get("tier", "?")
    role = enemy.get("role", "")
    rarity = enemy.get("rarity", "")
    tags = ", ".join(enemy.get("tags", []))
    stats = enemy.get("stat_block", {})
    hp = stats.get("hp", {}).get("max", "?")
    defense = stats.get("defense", {})
    dv_base = defense.get("dv_base", "?")
    idf = defense.get("idf", 0)
    dmg = stats.get("damage_profile", {})
    baseline = dmg.get("baseline", {})
    spike = dmg.get("spike", {})
    base_str = f"{baseline.get('dice','?')}{baseline.get('flat','')}"
    spike_str = f"{spike.get('dice','?')}{spike.get('flat','')}"
    lore = enemy.get("lore", {})
    one_liner = lore.get("one_liner", "")
    return "<br>".join([
        f"**{name}** (Tier {tier} / {role} / {rarity})",
        f"Tags: {tags}" if tags else "",
        f"HP {hp}; DV {dv_base}, IDF {idf}",
        f"Dmg: {base_str} / {spike_str}",
        one_liner
    ])


def write_grid_by_tier(bestiary, out_dir, columns):
    tiers = {}
    for enemy in bestiary:
        tiers.setdefault(enemy.get("tier", "?"), []).append(enemy)
    out_dir.mkdir(parents=True, exist_ok=True)
    generated = []
    for tier, enemies in tiers.items():
        enemies_sorted = sorted(enemies, key=lambda e: e.get("name", e.get("id", "")))
        cards = [render_enemy_card(e) for e in enemies_sorted]
        rows = [cards[i:i+columns] for i in range(0, len(cards), columns)]
        lines = ["# Tier {} Enemies".format(tier), "", "| " + " | ".join([""]*columns) + " |", "| " + " | ".join(["---"]*columns) + " |"]
        for row in rows:
            while len(row) < columns:
                row.append("")
            lines.append("| " + " | ".join(row) + " |")
        path = out_dir / f"tier-{tier}-beasts.md"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        generated.append(path)
    return generated


def main():
    root = Path(__file__).parent
    # config
    cfg = {}
    cfg_path = root / "config.json"
    if cfg_path.exists():
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        except Exception:
            cfg = {}
    md_mode = cfg.get("markdown_mode", "both")  # "single", "grid", "both"
    md_columns = cfg.get("markdown_columns", 3)

    archetypes = json.loads((root / "archetype.json").read_text(encoding="utf-8"))
    data = json.loads((root / "enemy.json").read_text(encoding="utf-8"))

    arch_list = archetypes.get("archetypes", [])
    arch_map = {a.get("id"): a for a in arch_list}
    meta = data.get("meta", {})
    enemies = list(data.get("enemies", []))

    # Load any beast JSON files (single enemy object or list or {"enemies": [...]})
    beasts_dir = root / "bestiary" / "beasts"
    if beasts_dir.exists():
        for beast_file in beasts_dir.glob("*.json"):
            try:
                beast_data = json.loads(beast_file.read_text(encoding="utf-8"))
            except Exception:
                continue
            if isinstance(beast_data, dict) and "enemies" in beast_data:
                enemies.extend(beast_data.get("enemies", []))
            elif isinstance(beast_data, list):
                enemies.extend(beast_data)
            elif isinstance(beast_data, dict):
                enemies.append(beast_data)

    bestiary = []
    for enemy in enemies:
        archetype_id = enemy.get("archetype_id")
        arch_defaults = arch_map.get(archetype_id, {}).get("defaults", {})
        overrides = enemy.get("overrides", {})

        resolved = deep_merge(arch_defaults, overrides)
        merged_enemy = {
            **{k: v for k, v in enemy.items() if k not in {"overrides"}},
            "resolved_archetype": resolved,
        }
        bestiary.append(merged_enemy)

    out = {"meta": meta, "enemies": bestiary}
    (root / "bestiary.json").write_text(json.dumps(out, indent=2), encoding="utf-8")

    # Write Markdown cards
    md_dir = root / "bestiary"
    md_dir.mkdir(parents=True, exist_ok=True)
    # markdown output modes
    generated_grid = []
    if md_mode in {"single", "both"}:
        for enemy in bestiary:
            eid = enemy.get("id", "unknown").replace(".", "_")
            md_path = md_dir / f"{eid}.md"
            md_path.write_text(render_enemy_md(enemy, arch_map), encoding="utf-8")
    if md_mode in {"grid", "both"}:
        generated_grid = write_grid_by_tier(bestiary, md_dir, md_columns)

    # Copy grid outputs to wiki if present
    wiki_dir = root.parent / "docs" / "wiki"
    if wiki_dir.exists() and generated_grid:
        wiki_dir.mkdir(parents=True, exist_ok=True)
        for src in generated_grid:
            shutil.copy(src, wiki_dir / src.name)


if __name__ == "__main__":
    main()
