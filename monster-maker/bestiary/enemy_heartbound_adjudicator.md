# Heartbound Adjudicator

- **ID:** `enemy.heartbound.adjudicator`
- **Archetype:** Aberrant (`archetype.aberrant`)
- **Tier/Role/Rarity:** 5 / executioner / boss
- **Tags:** heartbound, aberrant, boss
- **HP:** 70
- **Defense:** DV 18, IDF 3
- **Damage:** baseline 2d8 0, spike 3d8 0

## Lore
- It watches you like the Dungeon does.
- Dungeon voice: Show me something new.
- GM notes: Mutates as Blood Marks accumulate.

## Moves
- **Final Edict** (attack) - RP 2, CD 2, dmg: 3d8+0 (spike), effects: {"type": "primed"}
  - On miss: The Dungeon murmurs in disappointment.
  - Text: A killing declaration — dangerous even to survive.

## Behavior (Archetype)
- Opening: Read The Room
- Default loop: If blood mark gte=3, Mutation Response, Base Pattern
