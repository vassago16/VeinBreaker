# Goblin Shieldbearer

- **ID:** `enemy.goblin.shieldbearer`
- **Archetype:** Defender (`archetype.defender`)
- **Tier/Role/Rarity:** 1 / defender / common
- **Tags:** goblin, shield, guard
- **HP:** 12
- **Defense:** DV 12, IDF 1
- **Damage:** baseline 1d4 0, spike 1d6 0

## Lore
- Squats behind a slab and swats patterns.
- Dungeon voice: Same move, same mistake.
- GM notes: Forces Guard Break or varied chains.

## Moves
- **Shield Bash** (attack) - RP 1, CD 1, dmg: 1d4+0 (baseline), effects: stagger
  - On miss: Turtles back down, resetting stance.
  - Text: Bash that staggers repeat offenders.

## Behavior (Archetype)
- Opening: Raise Guard
- Default loop: If repeat count gte=2, Punish Repeat, Guard Counter
