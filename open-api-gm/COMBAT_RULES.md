# Veinbreaker Combat Rules (As Implemented)

This document describes the combat behavior **as currently implemented in code**, not aspirational design.

## Core Dice

- **To-hit / contests**: `2d10` is used anywhere the engine previously used a `d20` for rolls.
- **Advantage / Disadvantage (d10 pools)**:
  - `disadvantage`: roll `3d10`, keep **highest + lowest**
  - `severe disadvantage`: roll `4d10`, keep **highest + lowest**
  - `extreme disadvantage`: roll `4d10`, keep **two lowest**
  - `advantage`: roll `3d10`, keep **two highest**
  - `severe advantage`: roll `4d10`, keep **two highest**
  - `extreme advantage`: roll `4d10`, keep **two highest**
- **Common damage dice**: ability dice vary per ability; some fixed dice are used in specific rules:
  - Perfect parry counter damage: `1d4`
  - Perfect parry healing: `1d6 × tier`

## Combat Loop (High-Level)

- The game runs in rounds with a player side and enemy side.
- The player declares a **chain** of abilities (up to a max length; currently surfaced as 6 in the web UI).
- Chains resolve link-by-link; interrupts can occur depending on enemy window policy.
- End of round: status ticks (Bleed, Radiant Burn, Radiance healing), then HUD refresh.

## Character Creation (Web)

- Choose a **path**, then pick **1 resolve ability**, then pick **3 tier-1 abilities** (at least one must match your chosen path).

## Chain Resolution (Newrules Engine)

During chain resolution:

- **One attack roll is reused per chain** for all **non-movement** links.
  - If the previous **non-movement** link **missed**, the next non-movement link **rerolls `2d10` once** and that new roll becomes the reused roll for the remainder of the chain (until another miss triggers a reroll).
  - If the chain is **all movement**, no attack roll is made; each movement link applies its `resourceDelta` and any `effects.on_use` (including `heal`/`status`) and does not do hit/miss bookkeeping.
- Per link, the engine resolves hit/miss, updates meters, and applies ability effects.
- **Momentum cap**: `8` (clamped).

### Link Meter Changes (authoritative in chain engine)

For each link:

- If the link **hits**:
  - Defender Momentum: `+1` for links 1–2, `+2` for link 3+
  - Aggressor Balance: `+2`
- If the link **misses**:
  - Defender Momentum: `-1`
  - Aggressor Balance: `+1`

These are applied regardless of what the ability itself does via effects/tags.

### Tempo Reward (implemented)

- If the **player** hits with an **attack** link on **link 3+**, gain `+1 RP` (clamped to RP cap).

## Attack and Defense Math

### Ability resolution engine (legacy path used by many actions)

- Attack roll: `2d10 + stat_mod(ability.stat)` (if enabled) + temp attack bonus.
- Damage: ability’s `damage` effect dice + stat mod (if enabled) + heat bonus + flat bonus from damage effect.
- Defense target:
  - If a defense d-roll is provided: contested `defense_roll = d + enemy_idf + enemy_momentum + temp bonuses`
  - Otherwise: static `dv_base + enemy_idf + enemy_momentum + temp bonuses`
- **Crit**: if the attack hits and `to_hit >= defense_target + 5` (i.e., 5+ above the modified DV).

### Hard-Coded To-Hit Modifiers

- **`stat_mod(score)` table** (used when `addStatToAttackRoll` is enabled; score clamps down to nearest listed key):
  - `0:-5, 1:-4, 2:-4, 3:-4, 4:-3, 5:-2, 6:-2, 7:-1, 8:-1, 10:0, 11:0, 12:1, 13:1, 14:1, 15:2, 16:2, 17:3, 18:4, 19:4, 20:5, 21:5, 22:6`
- **Temp attack bonus**: `temp_bonuses.attack` is added to the attacker’s to-hit total (set by `attack_bonus` effects).
- **Chain engine (newrules)**: for non-movement links, the attack total adds encounter meter `balance` (in addition to `temp_bonuses.attack`); heat does **not** affect to-hit.
- **Execution Strike (newrules)**: when the target is Primed, applies a fixed `+4` to-hit bonus (“prime bonus”); after the roll is evaluated, applies a fixed `-2` balance penalty to the attacker.

### Heat bonus to damage (on hit)

- On a successful hit, heat is incremented by `+1` (projected).
- Damage then receives a heat bonus based on projected heat:
  - `heat_bonus = clamp(projected_heat - 1, 0..4)`

## Resources / Meters

The implementation uses two overlapping concepts:

- `character["resources"]` (persisted/legacy storage)
- Encounter-scoped “combat meters” in `engine.combat_state` (used when `_combat_key` is present)

Common meters:

- **HP**: `resources.hp` (with optional `resources.hp_max`) for players; enemies may use `hp.current/max` or `hp` depending on path.
- **RP**: stored as `resources.resolve`; in encounter mode also mirrored into combat meter `rp` with cap `rp_cap`.
- **Heat / Momentum / Balance**: encounter meters (when in encounter) and/or `resources.*` in legacy mode.
- **Radiance**: stored as `resources.radiance` (used for end-of-round healing).
- **IDF** (player): base interrupt defense factor derived from POW/STR: `IDF = clamp(1 + floor((POW-10)/2), >=0)` (so POW 8 -> 0, POW 10 -> 1, POW 12 -> 2).
- **Blood Marks** (permanent until a future mechanic removes them):
  - `1` mark: `+1` passive damage vs **wounded** foes (target `< 50%` HP).
  - `2` marks: `+1 RP` on **crit** (hit by 5+ over modified DV); if the target is **elite**, it reacts aggressively.
  - `3` marks: `+1` to **Execution Strike** rolls; “Hunter becomes aware” (a clock starts; not yet otherwise implemented).

### Start-of-turn upkeep

At the start of the player’s turn:

- Resolve regen: `+2 RP` (clamped to cap).
- Pool resources refill (martial/shadow/magic/faith), derived from attributes.

## Status Effects

Status storage:

- Many statuses use `target["statuses"][name] = {stacks, duration}`.

### End-of-round ticking

At end of round:

- **Bleed**:
  - Deals damage equal to stacks (`1 damage per stack`)
  - Then decays by `-1 stack`
  - Expires when stacks reach 0 or duration ends
- **Radiant Burn**:
  - Deals damage equal to stacks (`1 damage per stack`)
  - Does not have special decay logic beyond duration

### Stagger (Roll Penalty)

- If the acting entity has **Stagger** stacks (encounter status):
  - `1` stack: `disadvantage` on `2d10` rolls
  - `2` stacks: `severe disadvantage` on `2d10` rolls
  - `3+` stacks: `extreme disadvantage` on `2d10` rolls

## Radiance (Healing Buff)

If the player has `resources.radiance > 0`, then at end of round:

- Heal `+1 HP` for every current Radiance stack (healing happens **before** decay).
- Then Radiance decays by `-1`.

## Interrupts / Perfect Parry

### Interrupt windows

Enemy interrupt behavior is driven by resolved archetype interrupt windows and a per-round interrupt budget.

### Perfect interrupt / perfect parry outcome

On a **perfect interrupt** (perfect parry):

- Player gets a dedicated visceral UI overlay.
- Counter damage is applied: `1d4` to the chain owner.
- Player healing is applied: `1d6 × tier` (flat roll multiplied by player tier).

## Tier Progression and Stat Gains

### Tier 2 attainment (current rule)

When the player attains **Tier 2** (currently triggered if they have `3+ Veinscore`, and also by total Vein spent thresholds):

- Show the message: **“Tier 2 attained.”**
- Increase `resources.hp_max` by `+10` (current HP clamps to max, no free overheal).
- Set `resources.resolve_cap` to `7` (RP cap).
- Safe-room shop offers immediately include Tier 2 abilities (offers are filtered by `character.tier`).

### Safe room ability offers

- The shop offers abilities at `tier <= character.tier` that the character does not already own.
- Costs scale with ability tier (`cost = max(1, tier)`).
- **Stat training**: spend `3 Vein` to increase any one attribute (`POW/AGI/MND/SPR`) by `+1`.

## Ability Effect Codification (Supported Types)

The runtime supports these structured effect types (as of current code):

- `damage` (via `effects.on_hit` parsing for dice/stat)
- `reduce_damage`
- `resource_delta`
- `resource_set`
- `heal`
- `status` / `buff` (stored in `target.statuses`)
- `attack_bonus`, `defense_bonus`, `idf_bonus` (stored in `target.temp_bonuses`)

## Open Tuning Ideas (Not Implemented)

- Tighten the meter economy: define clear roles for Heat/Momentum/Balance (what each is “for”), then tune caps/bonuses so players can plan around them.
- Add more enemy variety at Tier 1–2: moves that punish repeats, punish long chains, or force movement so “best chain” isn’t always the same.
- Improve interrupt window telegraphing: show “danger timing” clearly so interrupts feel earned, not random.
- Make stances and statuses do more in runtime (not just cosmetic): meaningful ongoing effects/choices each round.
- Add post-fight rewards/pressure that depend on performance (damage taken, perfect defenses, speed) so players care about more than winning.
- Consolidate duplicated/overlapping systems (resources vs combat meters) to avoid desync and make tuning predictable.



things to implement:

stagger-
disadvantage
sever disadvantage
advante
sever advantage
