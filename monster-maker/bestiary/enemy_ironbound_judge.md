# Ironbound Judge

- **ID:** `enemy.ironbound.judge`
- **Archetype:** Defender (`archetype.defender`)
- **Tier/Role/Rarity:** 4 / warden / elite
- **Tags:** ironbound, guardian
- **HP:** 48
- **Defense:** DV 16, IDF 2
- **Damage:** baseline 2d6 0, spike 2d8 0

## Lore
- It decides when your turn is over.
- Dungeon voice: ENOUGH.
- GM notes: Hard counter to long chains and sloppy execution.

## Moves
- **Judgement Break** (attack) - RP 1, CD 1, dmg: 2d6+0 (baseline), effects: {"type": "stagger", "stacks": 2}
  - On miss: Steel rings loudly.
  - Text: Ends overlong chains decisively.

## Behavior (Archetype)
- Opening: Raise Guard
- Default loop: If repeat count gte=2, Punish Repeat, Guard Counter
