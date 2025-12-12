# 🩸 **SECTION 8 — RESOLVE ACTIONS**

## 

Resolve Actions are a universal set of high‑tempo combat techniques available to all VeinBreakers. They are **not Path abilities** and **not chain actions**. Instead, they are used during the *resolution* of a declared chain to manipulate Rhythm, positioning, or timing.

Resolve Actions cost **Resolve (RP)**, may have **cooldowns**, and each specifies a **timing window** where it may be used.

```
[DUNGEON NOTICE]
"Resolve is rhythm. What you do with it… is entertainment."
```

## **8.1 What Is a Resolve Action?**

A Resolve Action is:

- Performed **between actions** of your declared chain
- Costs **Resolve (RP)** only (no Pool)
- Has **cooldowns**
- Uses **timing tags** (Attack Window, Defense Window, Any Window)
- Does **not** increase Balance penalty
- Does **not** replace your declared chain

They modify the *context* of a chain, not the chain itself.

---

## **8.2 Resolve Action Timing Windows**

Each Resolve Action specifies when it can be used:

- **[Attack Window]** — Immediately after an attack resolves.
- **[Defense Window]** — When you are hit or threatened.
- **[Any Window]** — Between any two declared actions.
- **[End‑of‑Chain]** — After your final declared action resolves.

---

## **8.3 Core Resolve Actions (Tier 0 Resolve Kit)**

All new characters begin with these six techniques.

### **1. Disengage — Resolve Action**

**Cost:** 3 RP\
**Cooldown:** 1 round\
**Tag:** [Defense Window]\
**Effect:** End your chain immediately before the next declared action resolves.

### **2. Balance Surge — Resolve Action**

**Cost:** 2 RP\
**Cooldown:** None\
**Tag:** [Any Window]\
**Effect:** Set your Balance to **0** without ending the chain.

### **3. Rhythm Break — Resolve Action**

**Cost:** 2 RP\
**Cooldown:** 2 rounds\
**Tag:** [Defense Window]\
**Effect:** Cancel the next Interrupt attempt automatically.

### **4. Momentum Anchor — Resolve Action**

**Cost:** 1 RP\
**Cooldown:** None\
**Tag:** [Any Window]\
**Effect:** Gain **+1 Momentum** immediately.

### **5. Shift Footing — Resolve Action**

**Cost:** 1 RP\
**Cooldown:** None\
**Tag:** [Attack Window]\
**Effect:** Move 1 zone without altering Balance.

### **6. Greed Burst — Resolve Action**

**Cost:** 2 RP\
**Cooldown:** None\
**Tag:** [Attack Window]\
**Effect:** Add **+2 to the next Attack Value** of this chain.

---

## **8.4 How Resolve Actions Interact With Rhythm**

Resolve Actions allow real‑time modulation of Rhythm:

- **Balance Control** → Balance Surge (or Heat Purge synergy)
- **Heat Synergy** → Greed Burst before Heat Burst
- **Momentum Boosts** → Momentum Anchor before dangerous Interrupt windows
- **Chain Survival** → Disengage avoids lethal follow‑ups

They offer tactical flexibility without removing consequences of the Chain Declaration model.

---

## **8.5 Cooldowns & Limits**

Resolve Actions typically:

- Have **short cooldowns** (1–2 rounds)
- Cannot be spammed
- Are designed as *tempo tools*, not replacements for Abilities

Cooldowns reset at the start of your turn unless stated otherwise.

---

## **8.6 Expanding Resolve Actions (Tiers, Loot, Gifts)**

Resolve Actions may be unlocked or discovered through:

- Dungeon gifts
- Achievements
- Tier advancement
- Boss rewards
- Strange merchants

Higher‑tier Resolve Actions will offer more advanced timing manipulations.

---

## Resolve Actions & Interrupt Timing — Definitive Mapping

Resolve Actions interact with Interrupts in **strict, limited timing windows**.  
They may **prevent damage**, but they may **never undo it**.

This section defines exactly **when Resolve Actions may be used** relative to Interrupt attempts and chain failure.

---

## Core Invariant (Always True)

> **Any damage taken during a declared chain ends that chain.**

Resolve Actions cannot reverse this.

---

## Interrupt Timeline (Authoritative Order)

When a defender attempts an Interrupt, resolution proceeds in this order:

1. **Interrupt Window Opens**  
   The attacker has created exposure (miss, negative Balance, overcommit, etc.)

2. **Defense Window Resolve Actions (Optional)**  
   The acting player may use Resolve Actions tagged **[Defense Window]**

3. **Interrupt Contest (A3)**  
   Enemy AV vs Player DV is rolled

4. **Damage Resolution**  
   - If damage is dealt → chain ends immediately
   - If damage is fully prevented → chain may continue

5. **Post-Resolution Windows**  
   Any valid [Any Window] or [End-of-Chain] Resolve Actions may trigger

---

## What Resolve Actions CAN Do

Resolve Actions may:

- **Cancel an Interrupt attempt before it resolves**  
  (e.g., *Rhythm Break*)

- **Increase Defense Value before the Interrupt roll**  
  (e.g., *Momentum Anchor*)

- **End your chain voluntarily before damage occurs**  
  (e.g., *Disengage*)

- **Stabilize Rhythm after a successful defense**  
  (e.g., *Balance Surge after Perfect Defense*)

Resolve Actions operate **around** the Interrupt — not inside it.

---

## What Resolve Actions CANNOT Do

Resolve Actions may **never**:

- Be used **after damage is dealt**
- Reverse a chain that has already ended
- Negate HP loss retroactively
- Replace a failed defense roll
- Convert damage into a lesser penalty

Once damage occurs, the window is closed.

---

## Resolve Actions by Timing Tag

### [Defense Window]

May be used:
- When an Interrupt is declared
- Before the Interrupt contest resolves

May NOT be used:
- After damage is applied

Examples:
- Rhythm Break
- Disengage

---

### [Any Window]

May be used:
- Between actions in a chain
- After a successful defense
- After an Interrupt attempt that dealt no damage

May NOT be used:
- Mid-roll
- To retroactively change outcomes

Examples:
- Momentum Anchor
- Balance Surge

---

### [Attack Window]

May be used:
- After an attack action resolves
- Never during an Interrupt sequence

Examples:
- Greed Burst
- Shift Footing

---

### [End-of-Chain]

May be used:
- Only if the chain ends without damage
- Never triggered by forced chain failure

---

## Interaction with Perfect Defense

- Perfect Defense negates damage
- If damage is negated, the chain may continue
- Resolve Actions may be used after Perfect Defense if timing allows

Perfect Defense is the **only** way to survive an Interrupt without ending the chain once the roll resolves.

---

## Design Intent (Clarification)

Resolve Actions exist to:
- reward anticipation
- preserve rhythm under pressure
- provide controlled exits

They do **not** exist to:
- erase failure
- replace defensive mastery
- enable reaction spam

If a Resolve Action appears to negate damage after it has occurred, it is being used incorrectly.

---

### END — Resolve Actions & Interrupt Timing

# 

