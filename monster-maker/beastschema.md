# Bestiary Schema (v1)

Readable guide to the fields used by the bestiary JSON files.

## Top-Level
- **meta** (required): metadata and defaults.
  - **schema** (string): e.g., `veinbreaker.bestiary.v1`.
  - **system_rules** (object, recommended):
    - **resolve.regen_per_turn** (int): default 2.
    - **interrupt_margin.break_chain_on_margin_gte** (int): default 5.
    - **interrupt_margin.critical_interrupt_on_margin_gte** (int): default 10.
  - **archetype_source** (string, optional): e.g., `archetype.json`; load archetypes before enemies.
- **enemies** (array, required): list of enemy objects.

## Enemy Object (per entry in `enemies[]`)
### Identity
- **id** (string, required): unique, e.g., `enemy.faction.slug`.
- **name** (string, required): display name.
- **version** (string, optional): for balancing patches.
- **tier** (int, required): typical 1–5.
- **role** (string, required): descriptive role (e.g., harasser, defender, boss).
- **rarity** (string, required): e.g., common, uncommon, elite, boss.
- **tags** (array<string>, optional): search/filter tags.

### Archetype Binding
- **archetype_id** (string, required): references an entry in `archetype.json`. Behavior inherits from the archetype; use overrides to tweak.

### Lore
- **lore.one_liner** (string, optional): card hook.
- **lore.dungeon_voice** (string, optional): flavor quote.
- **lore.notes_gm** (string, optional): GM intent/usage.

### Stat Block
- **stat_block.hp.max** (int, required)
- **stat_block.defense.dv_base** (int, required)
- **stat_block.defense.idf** (int, required)
- **stat_block.damage_profile** (object, required)
  - **baseline** (object): `{ dice: "1dX", flat: int }`
  - **spike** (object, optional): same shape

### Moves (array, required)
Each move:
- **id** (string, required): unique within enemy (shared IDs allowed across enemies).
- **name** (string, required)
- **type** (string, required): e.g., attack, utility, movement, reaction.
- **cost.rp** (int, optional)
- **cooldown** (int, required; 0 = spammable; null = stance)
- **to_hit.av_mod** (int, required)
- **on_hit.damage** (string, optional): references damage_profile key (e.g., `baseline`, `spike`) or custom.
- **on_hit.effects** (array, optional): effect objects or strings; effect object suggested fields: `type`, `stacks`, `notes`.
- **on_miss.notes** (string, optional)
- **card_text** (string, optional but recommended)

### Overrides (optional)
- **overrides** (object): deep-merged over archetype defaults. Arrays replace by default unless you add patch operators.
- Common usage: `overrides.rhythm_profile.interrupt.windows` to change interrupt triggers.

### Rhythm Profile (usually inherited from archetype; can be overridden)
- **rhythm_profile.interrupt**: budget, reserve, timing_bias, windows[], margin_rules.
  - **windows[]**: `after_action_index` (array<int>), `trigger_if` (object conditions), `weight` (0–1), `notes`.
  - **margin_rules**: `break_chain_on_margin_gte`, `critical_interrupt_on_margin_gte` (fallback to meta if missing).
- **rhythm_profile.pressure**: toggles to punish repeats/long chains/movement, reward perfect defense; each has `enabled`, optional thresholds, optional `bias`.
- **rhythm_profile.state_interactions**: how it inflicts/resists Balance/Heat/Momentum/Resolve effects.
- **rhythm_profile.primed_and_execute**: `primed_conditions_used` (e.g., hp_le_25, vulnerable_3, stagger_2); `execute_resistance.dv_bonus_if_primed`.

### Optional Extras
- **traits** (array): passive rules text.
- **drops** (object): loot hooks (relic_chance, loot_table_refs, etc.).
- **card_view** (object): presentation-only; can be generated.

## Engine Processing Order (recommended)
1. Load `meta.system_rules`.
2. Load archetypes from `meta.archetype_source`.
3. For each enemy:
   - Start from archetype defaults.
   - Overlay enemy fields.
   - Apply `overrides` last.
4. Use `stat_block` for math, `rhythm_profile` for behavior, `moves` for actions.

## Minimal Valid Enemy Checklist
- `id`, `name`, `tier`, `role`, `rarity`
- `archetype_id`
- `stat_block.hp.max`
- `stat_block.defense.dv_base`, `stat_block.defense.idf`
- `stat_block.damage_profile.baseline`
- At least one move in `moves[]`
