# Additional Notes

## How Players Gain IDF
IDF is temporary, contextual, and earned.

- **Perfect Defense:** Perfect Parry/Dodge/Block often grant +1 Momentum and +1 IDF (usually until end of turn or next interrupt).
- **Stances:** Defensive/rooted stances grant +1 IDF (sometimes conditional, e.g., vs Heavy/Interrupts).
- **Equipment:** Shields, wards, conduits can grant flat +1 IDF or conditional IDF (vs spells, interrupts, movement punishers).
- **Buffs:** Defense Up, IDF Up, certain Faith/Utility abilities.
- **Boons/Relics:** Rare, usually conditional (e.g., “+1 IDF while at Positive Balance”).

## Core Design Principle for Traps
Traps use existing systems (A3 contests, Balance/Heat/Momentum/Resolve). They create decision pressure, not “gotcha” damage. Think of traps as environmental enemies with no HP.

### Trap Resolution (Clean Rule)
Use A3 contests:
- Trap AV = d20 + trap modifier (tier-scaled).
- Player DV = normal DV (AGI/MND/IDF/etc., context-driven).
  - Dodge traps → AGI DV; mental/arcane traps → MND/IDF DV; faith wards → IDF/Radiance DV.

### Triggering Traps
- **Interrupt-style (common):** After action 2+, on movement, on chain length ≥ X, on miss, on perfect defense (rare).
- **Zone traps:** Passive pressure (e.g., fire floor, slick ground) that applies state pressure, not direct attacks.
- **Triggered traps:** One-shot beats (first entry, execution event, Blood Mark threshold, arena phase shift); roll once, then disable/change form.

### On Hit (Preferred Order)
Harm should favor state over raw damage:
- Balance damage, state effects, Heat disruption, Momentum crash, chain break, damage (only if thematic/greed/Tier 3+).

### RP Interaction
- **Reacting:** Spend RP for Resolve defense, special dodge/parry/ward, negate/reduce effects.
- **Disabling:** Costs an action; optionally RP to auto-succeed/reduce future triggers/turn trap into a weapon. Default: disabling ends chain or applies −2 Balance unless paid (e.g., 1 RP to continue).

### Trap Tiers
Traps scale by tier, not location:
| Tier | Role                          |
| ---- | ----------------------------- |
| 1    | Teaches rhythm mistakes       |
| 2    | Punishes greed                |
| 3    | Forces RP decisions           |
| 4    | Alters arena rules            |
| 5    | Narrative threats / Hunter tools |

Tier 1 traps shouldn’t kill; Tier 3 should cost resources; Tier 4 should change the fight.

### Example Trap (Tier 1)
```json
{
  "id": "trap.brumkin.floor_spines",
  "tier": 1,
  "tags": ["movement", "timing", "low_damage"],
  "interrupt": {
    "budget_per_round": 1,
    "windows": [
      { "after_action_index": [2,3], "trigger_if": { "player_moved": true } }
    ]
  },
  "attack": {
    "av_mod": 0,
    "on_hit": { "effects": [ { "type": "off_balance" }, { "type": "bleed", "stacks": 1 } ] },
    "on_miss": { "notes": "Player dances between the spikes." }
  },
  "disable": {
    "action_cost": 1,
    "balance_cost": -1,
    "rp_option": { "cost": 1, "effect": "disable_without_penalty" }
  }
}
```

### Golden Rule
If a player can say, “I should have known better,” the trap worked. If they say, “What just happened?” the trap failed.
