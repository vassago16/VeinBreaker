import json
import copy
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
            effects_str = ", ".join(effects) if effects else "none"
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


def main():
    root = Path(__file__).parent
    archetypes = json.loads((root / "archetype.json").read_text(encoding="utf-8"))
    data = json.loads((root / "enemy.json").read_text(encoding="utf-8"))

    arch_list = archetypes.get("archetypes", [])
    arch_map = {a.get("id"): a for a in arch_list}
    meta = data.get("meta", {})
    enemies = data.get("enemies", [])

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
    for enemy in bestiary:
        eid = enemy.get("id", "unknown").replace(".", "_")
        md_path = md_dir / f"{eid}.md"
        md_path.write_text(render_enemy_md(enemy, arch_map), encoding="utf-8")


if __name__ == "__main__":
    main()
