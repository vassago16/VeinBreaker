# Bone Shambler

- **ID:** `enemy.shambler.bone`
- **Archetype:** Juggernaut (`archetype.juggernaut`)
- **Tier/Role/Rarity:** 1 / juggernaut / uncommon
- **Tags:** undead, heavy
- **HP:** 18
- **Defense:** DV 11, IDF 0
- **Damage:** baseline 1d6 0, spike 1d8 1

## Lore
- Slow pile of bone that hates long chains.
- Dungeon voice: Keep hitting. See what breaks first.
- GM notes: Shows flurry resistance and greedy-chain punish.

## Moves
- **Heavy Slam** (attack) - RP 1, CD 1, dmg: 1d8+1 (spike), effects: off_balance
  - On miss: Telegraphs again; still looming.
  - Text: Slow crush that knocks footing loose.

## Behavior (Archetype)
- Opening: Telegraphed Swing
- Default loop: If chain length gte=6, Crush Punish, Heavy Slam
