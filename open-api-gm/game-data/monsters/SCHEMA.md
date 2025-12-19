# VeinBreaker Monster (Enemy) Data Schema

This documents what the *runtime* currently supports for enemies loaded from `game-data/monsters/bestiary.json`.

## Top-level file shape

```json
{
  "meta": {
    "schema": "veinbreaker.bestiary.v1",
    "system_rules": {
      "enemy_hp": { "variance_pct": 0.2 },
      "resolve": { "regen_per_turn": 2 },
      "interrupt_margin": { "break_chain_on_margin_gte": 5, "critical_interrupt_on_margin_gte": 10 }
    }
  },
  "enemies": [ /* enemy objects */ ]
}
```

### `meta.system_rules.enemy_hp`

- `variance_pct` (`number`, default `0.0`): if an enemy only defines `stat_block.hp.max`, each spawned encounter instance randomizes max HP within `max * (1±variance_pct)` and sets current HP to that value.

Per-enemy overrides are supported via `stat_block.hp.variance_pct` (or `stat_block.hp.variance`).

## Enemy object (supported fields)

```json
{
  "id": "enemy.brumklin.skitter",
  "name": "Brumklin Skitter",
  "tier": 1,
  "role": "harasser",
  "rarity": "common",
  "tags": ["brumkin", "small", "scout"],

  "archetype_id": "archetype.aggressor",

  "lore": {
    "one_liner": "…",
    "dungeon_voice": "…",
    "notes_gm": "…"
  },

  "stat_block": {
    "hp": { "max": 10 },
    "defense": { "dv_base": 5, "idf": 0 },
    "damage_profile": {
      "baseline": { "dice": "1d4", "flat": -1 },
      "spike": { "dice": "1d4", "flat": 0 }
    }
  },

  "moves": [
    {
      "id": "move.basic_attack",
      "name": "Skitter Slash",
      "type": "attack",
      "cost": { "rp": 1 },
      "cooldown": 0,
      "to_hit": { "av_mod": 0 },
      "on_hit": { "damage": "baseline", "effects": [] },
      "on_miss": { "notes": "…" },
      "card_text": "…"
    }
  ],

  "overrides": { "rhythm_profile": { "interrupt": { /* see below */ } } },
  "resolved_archetype": { "rhythm_profile": { "interrupt": { /* see below */ } } }
}
```

### Runtime-added fields (instance-only)

Spawned enemies get instance runtime fields added in `play._prime_enemy_for_combat()`:

- `hp`: `{ "current": int, "max": int }`
- `dv_base`: int (from `stat_block.defense.dv_base`)
- `idf`: int (from `stat_block.defense.idf`)

## Interrupt windows (supported)

The combat engine reads interrupt windows from:

- `enemy.resolved_archetype.rhythm_profile.interrupt.windows` (preferred)
- `enemy.interrupt_windows` (fallback)
- `enemy.ai.interrupt_windows` (fallback)

### Supported budget

If present, this is enforced:

- `enemy.resolved_archetype.rhythm_profile.interrupt.budget_per_round` (`int`): max number of interrupt *attempts* for that defender per round.

### Window formats

The engine supports two formats:

#### 1) New format (predicate DSL)

```json
{
  "when": "before_link",
  "if": { "type": "chain_index_at_least", "value": 1 },
  "chance": 0.35,
  "priority": 10
}
```

#### 2) Legacy format (currently used by `enemy.brumklin.skitter`)

```json
{
  "after_action_index": [2],
  "trigger_if": { "player_missed_last_action": true },
  "weight": 0.85,
  "notes": "Skitter is extra mean about misses."
}
```

Supported `trigger_if` keys:

- `player_missed_last_action` (bool)
- `chain_length_gte` (int)
- `player_heat_gte` (int)
- `blood_mark_gte` (int)

If a window contains unknown keys, it fails closed (no interrupt).

## Fields currently ignored (safe to keep, not wired yet)

The bestiary currently contains additional knobs (examples: `margin_rules`, `timing_bias`, pressure/AI notes). They are not yet used by the runtime unless explicitly listed above.
