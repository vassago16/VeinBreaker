===========================================
 VEINBREAKER CORE COMBAT LOOP (PSEUDOCODE)
===========================================

TURN START
----------
Momentum = 0
Balance = 0 (unless locked or affected by debuff)
RP += 3 (cannot exceed max RP cap)
If Heat Stabilized last turn: Heat = carried value (max 2)
Else: Heat = 0
Apply ongoing statuses (Bleed, Radiance, Stagger, etc.)
Tick cooldowns for abilities and Resolve Actions


===========================================
 1. PLAYER DECLARES CHAIN
===========================================
Player chooses:
    • Number of actions
    • Which actions (attacks, abilities, movement, utility)
    • Order of actions
    • Target(s)

Resolve Cost = 1 RP per declared action

IF RP < Resolve Cost:
      Reject chain → Player must declare a smaller valid chain

Chain declaration is now LOCKED IN.


===========================================
 2. FOR EACH ACTION IN THE CHAIN (LOOP)
===========================================

-------------------------------------------
Step 1 — Check Ability Cooldowns & Pool Costs
-------------------------------------------
IF ability.onCooldown:
      Chain FAILS → End turn

IF ability requires Pool points:
      IF Pool < cost:
            Chain FAILS → End turn
      ELSE:
            Pool -= cost


-------------------------------------------
Step 2 — A3 Contest (AV vs DV)
-------------------------------------------
Attacker rolls:
      AttackValue = d20 + offensive_modifiers + Balance_modifier

Defender rolls:
      DefenseValue = d20 + Momentum + IDF + situational_modifiers


-------------------------------------------
Step 3 — Resolve Outcome
-------------------------------------------
IF AttackValue ≥ DefenseValue:
      HIT:
         • Apply damage
         • Apply effects
         • Heat += 1 (or +2 on crit)

ELSE:
      MISS:
         • No damage
         • Chain continues normally

IF DefenseValue ≥ AttackValue + 5:
      PERFECT DEFENSE:
         • Defender Momentum += 1
         • Defender Balance += 1
         • Perfect Effect triggers (Riposte window, Radiance, Reflect, etc.)


-------------------------------------------
Step 4 — Rhythm Updates
-------------------------------------------
Apply Balance penalty for action (Light, Heavy, Ability, etc.)
If Movement Action:
      Either +1 Balance or halve negative Balance
Other rhythm-based effects apply as relevant.


-------------------------------------------
Step 5 — Enemy Interrupt Check
-------------------------------------------
IF this is the FIRST action:
      No Interrupt possible → Proceed to Step 6

Enemy may attempt Interrupt:
      InterruptValue_enemy = d20 + enemy_mods
      DefenseValue_player = d20 + Momentum + IDF + situational_mods

IF InterruptValue_enemy < DefenseValue_player:
      • Interrupt fails → chain continues

IF InterruptValue_enemy >= DefenseValue_player AND Margin < 5:
      • Player takes Interrupt damage/effects
      • Chain continues

IF InterruptValue_enemy >= DefenseValue_player + 5:
      • INTERRUPT SUCCESS:
              Chain immediately ENDS
              Apply Stagger/Vulnerable/etc.
              Heat resets (unless Stabilized)
              → Proceed to TURN END


-------------------------------------------
Step 6 — Resolve Action Window
-------------------------------------------
Player may use Resolve Actions if timing window is valid:
      • Balance Surge (reset Balance to 0)
      • Rhythm Break (cancel next Interrupt)
      • Momentum Anchor (+1 Momentum)
      • Greed Burst (+2 on next AV)
      • Shift Footing (movement without Balance penalty)
      • Disengage (end chain voluntarily)

IF Disengage used:
      → Chain ends immediately


-------------------------------------------
Step 7 — End Conditions Per Action
-------------------------------------------
IF HP <= 0:
      Trigger DEATHLINE

IF last declared action resolved:
      Chain ends

IF chain broken (invalid cost, cooldown, interrupt, disengage):
      Chain ends

Otherwise:
      LOOP back to next action.


===========================================
 TURN END
===========================================
Heat resets to 0 (unless Stabilized)
Momentum resets next turn
Balance resets next turn
Apply end-of-turn statuses
Advance cooldowns
Pass turn to next combatant

