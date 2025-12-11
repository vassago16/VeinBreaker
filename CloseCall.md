# Close Call — Veinbreaker 1v1 Log

## Character Creation
- **Path:** Martial (Stonepulse flavor) | **Weapon Tags:** Heavy/Blunt
- **Attributes:** POW 12, AGI 10, MND 8, SPR 8 | **HP:** 22 | **Resolve:** Max 5 (regen 3/turn)
- **Pools:** Martial 6, Shadow 4, Magic 4, Faith 4
- **Starting Rhythms:** Balance 0, Momentum 0, Heat 0
- **Tier 0 Actions:** Basic Attack (1 RP), Parry (reaction), Stonepulse Rhythm (utility, +1 to next melee attack this round)

- **Enemy:** Shadow Adept (Tier 0) — AGI 12, HP 20, Tags: Finesse/Slashing. Starts Balance 0, Momentum 0, Heat 0. Actions used: Hemocratic Strike (Bleed 1), Parry, Wound Mark (+1 to next Bleed).

## Round 1
**Your chain:** Attack / Attack / Rhythm (3 RP paid; start RP 5 → 2)
1) Attack: AV 15 vs DV 11 → hit. Damage 6. Heat 1. Balance -1. RP +1 → 3. Enemy HP 14.
2) Attack: AV 12 (14 base, -2 Balance) vs DV 12; enemy Parry DV 13 succeeds → deflected. No damage, Heat stays 1. Balance -2. (Parry failed earlier, so no Momentum gained.)
3) Stonepulse Rhythm: +1 to next Martial melee this round. RP -1 → 3. End: you HP 22, RP 3, Balance -2, Momentum 0, Heat 1.

**Enemy chain:** Attack / Wound Mark / Hemocratic Strike (3 RP paid; start RP 5 → 2)
1) Attack: AV 16 vs your DV 12 → hit. Damage 4. Bleed 1 applied. Heat 1. Balance -1. RP +1 → 3. Your HP 18.
   - Your Parry attempt fails (DV 13 vs AV 16); no Momentum gained.
2) Wound Mark: Next Bleed gains +1 stack. Balance steady. (RP still 3.)
3) Hemocratic Strike: AV 13 (14 base, -1 Balance) vs your DV 10 on failed Parry → hit. Damage 5. Heat 2. Balance -2. RP +1 → 4. Bleed now 2 (base 1 +1 from Wound Mark).

End of Round 1: Enemy HP 14, RP 4, Balance -2, Heat 2. You HP 13 (22 -4 -5), RP 3, Balance resets next turn, Momentum 0, Heat 1, **Bleed 2** ticking next round.

## Round 2
Start: Bleed 2 triggers (you to 11 HP). Reset Balance/Momentum/Heat to 0. RP 3 regen to cap 5. Enemy Balance reset 0, Heat 0, RP 4.

**Your chain:** Rhythm / Attack / Attack (3 RP paid; RP 5 → 2)
1) Stonepulse Rhythm: +1 to your next melee this round. Balance 0. RP 4.
2) Attack with Rhythm bonus: AV 15 vs DV 12; enemy Parry 14 fails. Hit for 6. Heat 1. Balance -1. RP net 4. Enemy HP 8.
3) Attack: AV 12 (14 base, -2 Balance) vs DV 12; no interrupt left. Hit for 7. Heat 2 (+1 dmg future). Balance -2. RP net 4. Enemy HP 1.

**Enemy chain:** Attack / Attack / Withdraw (3 RP paid; RP 4 → 1)
1) Attack: AV 15 vs your DV 12 (no Parry). Hit for 4. Heat 1. Balance -1. RP +1 → 2. You HP 7.
2) Attack: AV 13 (14 base, -1 Balance) vs your Parry DV 13; hit lands (AV ≥ DV). Damage 3. Heat 2. Balance -2. RP +1 → 3. You HP 4.
3) Withdraw: Disengages; Balance resets to 0.

End of Round 2: Enemy HP 1, RP 3, Balance 0, Momentum 0, Heat 2, disengaged. You HP 4, RP 4 (will regen to 5), Balance resets next turn, Heat 2, no Bleed.

## Round 3
Start: Balance/Momentum reset 0, RP to cap 5, Heat 2. Enemy at 1 HP, disengaged.

**Your action:** Execution (replaces next attack; costs 1 RP; auto -2 Balance; Heat drops to 0 after). AV roll 14 vs enemy DV roll 7 → success. Enemy Primed by low HP, so Execution finishes them. Gain +1 RP (to 5) and 1 Blood Mark. Balance resets after action; Heat 0.

## Result
- Victory with 4 HP remaining, RP 5, Balance 0, Momentum 0, Heat 0, Blood Mark 1.
- Enemy down from Execution.

## Notes
- Parry only grants Momentum on success; failed Parries in Round 1 and 2 did not grant Momentum.
- Wound Mark applied correctly to a Bleed-bearing attack (Hemocratic Strike) for Bleed 2.
- Balance penalties applied to AV for multi-attack chains; Rhythm bonus applied to the first attack after casting.





Built a Tier 3 Stonepulse martial using the abilities.json entries.

Character

Path: Stonepulse Martial (Tier 3)
Stats (suggested): POW 14, AGI 10, MND 8, SPR 8 → HP 24; Resolve max 8 (Tier 3 cap), regen 3/turn; Martial Pool 7; others 4
Weapon tags: Heavy/Blunt (enables Stagger interactions and Block/Parry tools)
Starting rhythms: Balance 0, Momentum 0, Heat 0
Ability Loadout (Stonepulse only, from abilities.json)

Tier 1: Pulse Strike (attack 1 RP, +1 to next melee on hit), Stoneguard Step (defense 1 RP), Stonepulse Rhythm (utility 1 RP, +1 attack to next melee, +1 RP, ally +1 Momentum)
Tier 2: Stonepulse Stance (stance 2 RP, +1 DEF/IDF, +1 Momentum at turn start), Resonant Break (attack 2 RP, 1d6+STR, Stagger 1; extra RP if in stance), Anchored Form (defense 2 RP, retaliate if 0 dmg, +Momentum), Stonepulse Focus (utility 2 RP, Attack Up + Defense Up, allies +1 IDF, +Momentum)
Tier 3: Sundering Crash (attack 3 RP, 1d8+STR; Stagger 1; if already Staggered, add Vulnerable 1; +2 dmg if Momentum ≥2), Steelguard Pivot (defense 3 RP; if 0 dmg, next attack +2 dmg; if Momentum ≥2, that attack has Advantage), Law of the Unshaken (utility 3 RP; next melee Advantage +3 dmg; in stance also apply Stagger 1; if Momentum ≥2, +5 dmg), Stonepulse Advance (movement 3 RP; remove cooldown from a T1/T2 Stonepulse ability; set Balance 0; gain +1 Momentum)
Play Pattern

Openers: Stonepulse Stance early to start gaining free Momentum each turn; Pulse Strike to set up +1 to hit.
Momentum engine: Use Stoneguard Step/Anchored Form to bank Momentum; Resonant Break applies Stagger and feeds RP if in stance.
Finisher line: Sundering Crash after Stagger is on the target; Law of the Unshaken before a big hit; Steelguard Pivot to flip defense into offense.
Cooldown management: Stonepulse Advance to refresh Pulse Strike/Resonant Break or your stance if stripped, while zeroing Balance.
Want a different stat line or a specific encounter loadout (e.g., swap Focus in/out), or should I script a sample turn-by-turn using this kit?

## Sample Turn-by-Turn (Tier 3 Stonepulse Demo)
**Your Build (Tier 3 Stonepulse):** POW 14, AGI 10, MND 8, SPR 8; HP 24; Resolve max 8 (regen 3/turn); Balance 0/Momentum 0/Heat 0. Abilities: Pulse Strike, Stoneguard Step, Stonepulse Rhythm, Stonepulse Stance, Resonant Break, Anchored Form, Stonepulse Focus, Sundering Crash, Steelguard Pivot, Law of the Unshaken, Stonepulse Advance.  
**Enemy:** Elite Stalker (HP 26, DV 12, heavy hits for 1d8+3), no special stance.  
Assumption: Each hit grants +1 RP and +1 Heat; each attack in a chain applies -1 Balance.

### Round 1
Start: RP 8; Balance 0; Momentum 0; Heat 0.  
Chain: **Stance / Pulse Strike / Law of the Unshaken** (RP spent: 2 + 1 + 3 = 6; RP left 2).
1) **Stonepulse Stance**: Enter stance (+1 DEF/IDF, future start-of-turn Momentum). Balance 0.  
2) **Pulse Strike**: AV 15 vs DV 12 → hit. Damage 1d4+3 = 6. Heat 1. Balance -1. RP +1 (now 3). Momentum +1 (was 0). Next melee this round gains +1 to hit.  
3) **Law of the Unshaken**: Buff next melee attack with Advantage and +3 dmg; in stance, that attack also applies Stagger 1. RP -3 (ends at 0). Balance unchanged.  
Enemy turn (brief): Stalker swings (1d8+3, AV 14 vs your DV 13 with stance). You opt not to burn a defense this turn. Takes 7 dmg (HP 24 → 17). No Momentum gained on your side.

### Round 2
Start: Stance grants +1 Momentum (now 2). RP regen +3 (0 → 3). Balance resets 0. Heat carries at 1. Law buff is pending for your next melee attack.  
Chain: **Sundering Crash / Anchored Form** (RP spent: 3 + 2 = 5; RP left 0).
1) **Sundering Crash** (buffed): Advantage to hit; AV 18 vs DV 12 → hit. Damage 1d8+3 (roll 6 = 9) +3 from Law +2 from Momentum≥2 = 14. Applies Stagger 1 (plus Law’s Stagger 1 → total Stagger 2). Enemy HP 26 → 12. Heat 2. Balance -1. RP +1 (now 1).  
2) **Anchored Form**: Defensive setup; reduce next incoming damage by 1d6, gain Retaliate if reduced to 0, gain +1 Momentum. RP -2 (net -1 → 0). Balance unchanged. Momentum now 3.
Enemy turn: Stalker attacks (AV 15). Anchored Form reduces damage by 1d6 (roll 4), final damage 6 (HP 17 → 11). Momentum already 3. Retaliate not triggered (damage not zero). Enemy suffers Stagger 2 (from your prior hit) on its next offensive roll.

### Round 3 (finisher line)
Start: Stance +1 Momentum (now 4). RP regen +3 (0 → 3). Balance resets 0. Heat 2. Enemy is Staggered 2 (likely Primed soon).  
Chain: **Resonant Break / Steelguard Pivot** (RP spent: 2 + 3 = 5; exceeds RP 3, so trim chain to a single finisher).  
Revised chain: **Resonant Break** only (RP spent 2; RP left 1).  
1) **Resonant Break**: AV 16 vs DV 11 (enemy Staggered 2) → hit. Damage 1d6+3 (roll 4 = 7) +2 Momentum≥2 bonus = 9. Applies Stagger 1 (stacking to 3+). Enemy HP 12 → 3. Heat 3. Balance -1. RP +1 (now 2). If in stance, gain +1 RP (GM call) → could be 3 total.  
Enemy is now at 3 HP and Staggered 3 (Primed if your table rules use Stagger 2+ as a Primed condition). Execution is now available; otherwise, a basic attack will close.

### Round 4 (cleanup)
Start: Stance +1 Momentum; RP to cap as needed; Balance resets 0; Heat 3 (option to Heat Burst).  
Chain: **Execution** (1 RP; auto -2 Balance; consumes Heat). Roll AV vs DV; with enemy Primed, success kills. If you prefer raw damage: **Pulse Strike** with Heat Burst for +3 dmg (Heat 3) will also finish the 3 HP remaining.

**Why this works**
- Stance early feeds Momentum and defense.  
- Law of the Unshaken + Sundering Crash front-loads a huge hit with Advantage, Stagger 2, and +dmg from Momentum.  
- Resonant Break cleans up with Stagger application and Momentum synergy; Execution is ready once Primed.  
- Stonepulse Advance (not shown) refreshes a key cooldown while zeroing Balance for longer fights.

## Sample Turn-by-Turn (Tier 3 Spellforged/Conduit Demo)
**Your Build (Tier 3 caster):** MND 14, POW 10, AGI 10, SPR 8; HP 20 (10 + POW 10); Resolve max 8 (regen 3/turn); Balance 0/Momentum 0/Heat 0. Abilities: Charge Bolt, Warding Pulse, Arcane Channel, Arcane Step, Surge Lance, Feedback Shield, Conduit Flow, Conduit Stance, Law of the Stormcore, Aetheric Reversal, Arcanum Overload, Arcane Transcendence.  
**Enemy:** Vanguard Bruiser (HP 28, DV 12, attacks for 1d8+4), no stance.  
Assumption: Each hit grants +1 RP and +1 Heat; each attack in a chain applies -1 Balance. Conduit Stance gives +1 Momentum when you cast (max +1/round).

### Round 1
Start: RP 8; Balance 0; Momentum 0; Heat 0.  
Chain: **Conduit Stance / Arcane Channel / Surge Lance** (RP spent: 2 + 1 + 2 = 5; RP left 3).
1) **Conduit Stance**: Enter stance (+1 Arcane IDF; refresh 1 Magic Pool/round; +1 Momentum when you cast, max +1/round). Balance 0.  
2) **Arcane Channel**: Next spell gains +1 to hit; gain +1 RP; gain +1 Momentum. RP net +1 (to 4). Momentum 1. Balance 0.  
3) **Surge Lance**: AV 16 (+1 from Channel) vs DV 12 → hit. Damage 1d6+INT (roll 4+2=6) +1 Momentum bonus (if GM allows “gain +1 Momentum” wording as +1 Momentum, not dmg). On hit, gain Arcane Charge (+1 dmg next spell). Heat 1. Balance -1. RP +1 (now 5). Momentum stays 1 (Conduit stance already gave +1 for casting this round).
Enemy turn: Bruiser swings (AV 15). You take 1d8+4 (roll 5=9) → HP 11. Momentum remains 1 (no defense used). Enemy Balance 0, Heat 0.

### Round 2
Start: Conduit Stance refreshes 1 Magic Pool. RP regen +3 (5 → 8 cap). Balance resets 0. Momentum resets 0 (stance will add +1 on first cast). Heat carries at 1.
Chain: **Conduit Flow / Arcanum Overload / Law of the Stormcore** (RP spent: 2 + 3 + 3 = 8; RP left 0).
1) **Conduit Flow**: +1 INT for 1 round; next spell +2 dmg; gain +1 Momentum. Momentum 1. Balance 0.  
2) **Arcanum Overload**: Next spell gains Advantage and +3 dmg; you take 1 self-dmg (HP 10). If Momentum ≥2, it would be +5 dmg, but currently 1. RP already paid. Balance 0.  
3) **Law of the Stormcore** (buffed by Flow + Overload + Arcane Charge): Advantage to hit; AV 18 vs DV 12 → hit. Damage: 1d8+INT (roll 6+2=8) +2 (Flow) +3 (Overload) +1 (Arcane Charge) = 14. Heat 2. Balance -1. RP +1 (now 1). On hit, chain a free 1d4 lightning bolt to another target (ignored here single target). Momentum remains 1.
Enemy HP: 28 → 14. Enemy turn: Bruiser attacks (AV 15). You opt **Warding Pulse** as reaction (cost 1 RP; but RP 1). Reduce dmg 1d4 (roll 3) → damage 6 (HP 4). If reduced to 0 you’d gain Momentum; here you don’t. Heat unchanged.

### Round 3 (cleanup)
Start: RP regen +3 (1 → 4). Balance resets 0. Momentum resets 0; Conduit Stance will give +1 on first cast. Heat 2.  
Chain: **Arcane Channel / Charge Bolt / Heat Burst** (RP spent: 1 + 1 + 0)  
1) **Arcane Channel**: Next spell +1 to hit; gain +1 RP; gain +1 Momentum (stance cap for the round). RP 5. Momentum 1. Balance 0.  
2) **Charge Bolt**: AV 15 vs DV 12 → hit. Damage 1d4+2 (roll 3+2=5) + Heat bonus (+2 dmg at Heat 2 if table allows) = ~7. Heat to 3. Balance -1. RP +1 (to 6). Momentum stays 1. Enemy HP 14 → 7.  
3) **Heat Burst**: Spend all Heat (3) for +3 dmg to the last hit (total that hit becomes ~10) and reset Balance to 0. Heat 0. RP already paid (0). Enemy HP ~4.  
Enemy turn: If still up (~4 HP), they attack; you can **Feedback Shield** (cost 2 RP) next round or finish with a simple Channel + Bolt.

### Round 4 (likely finish)
Start: RP 6 (regen to cap 8 if unused), Balance 0, Momentum 0, Heat 0.  
Chain: **Arcane Channel / Charge Bolt**. Channel gives +1 to hit, +1 RP, +1 Momentum; Bolt hits on AV 15 vs DV 12 for ~5–6 dmg. Enemy drops.

**Why this works**
- Conduit Stance + Channel builds Momentum and accuracy while refunding RP.  
- Overload + Flow + Arcane Charge supercharges Law of the Stormcore for a big spike with Advantage.  
- Heat Burst turns leftover Heat into burst damage and balance reset for cleanup.  
- Feedback/Warding let you trade RP to soften incoming hits; Transcendence can refresh T1/T2 tools and add Arcane Ward if the fight drags.
