# Veinbreaker Rules Lint
## Load-Bearing Invariants & Validation Checklist

This document defines rules that **must never be violated**.
If any item in this list fails, the system is no longer Veinbreaker.

Use this as:
- a pre-merge checklist,
- an AI debugging guide,
- or a design sanity test.

---

## 1. Chain Integrity

### Invariants
- A chain **must be declared before it resolves**
- Actions **cannot be added** after declaration
- A chain **cannot resume once ended**
- A miss **does not** end a chain
- **Any damage taken by the acting character ends the chain immediately**

### Fail Conditions
- A player continues a chain after taking damage
- An action is added mid-resolution
- A Resolve Action “saves” a chain after damage

---

## 2. Damage Is a Hard Failure

### Invariants
- Any HP loss counts as damage
- Damage is resolved immediately
- Damage cannot be reduced, converted, delayed, or rewritten
- Damage **always** ends the chain

### Fail Conditions
- “Chip damage” that does not end a chain
- Damage converted into another penalty
- Damage negated after being applied

---

## 3. Interrupt Scarcity

### Invariants
- Each defender may attempt **one Interrupt per round**
- Interrupts require exposure
- Interrupts never occur during declaration
- Interrupts are always contests
- Interrupts exist to **end chains**, not tax them

### Fail Conditions
- Multiple Interrupts from the same defender in one round
- Interrupts triggered without exposure
- Interrupts used as routine defense

---

## 4. Resolve Actions Are Not Actions

### Invariants
- Resolve Actions are **not declared**
- Resolve Actions do **not** consume action slots
- Resolve Actions cannot deal damage
- Resolve Actions cannot create or extend chains
- Resolve Actions cannot undo damage
- Resolve Actions require explicit timing windows

### Fail Conditions
- Resolve Actions used during declaration
- Resolve Actions granting extra attacks
- Resolve Actions reversing damage or chain end

---

## 5. Timing Is Law

### Invariants
- All abilities must respect phase timing
- Defense Window Resolve Actions occur **before** Interrupt rolls
- No Resolve Actions may be used after damage
- No actions occur mid-roll

### Fail Conditions
- “Last second” reactions after damage
- Retroactive stat modification
- Phase skipping or overlap

---

## 6. Perfect Defense Is Special

### Invariants
- Perfect Defense negates all damage
- Perfect Defense is the **only** way to survive an Interrupt and continue a chain
- Perfect Defense availability is tracked explicitly

### Fail Conditions
- Other mechanics behaving like Perfect Defense
- Implicit or assumed Perfect Defense
- Perfect Defense reused illegally

---

## 7. Resources Are Forward-Only

### Invariants
- Resolve cannot go negative
- Resolve is a planning currency, not a reaction pool
- Momentum affects defense, not immunity
- Heat increases risk, not safety
- Balance modifies exposure, not success guarantees

### Fail Conditions
- Spending Resolve to erase failure
- Momentum preventing damage by itself
- Heat being spent retroactively

---

## 8. Death Is Additive, Not Resetting

### Invariants
- HP reaching 0 is death
- Death ends the encounter
- Player respawns at last Safe Room
- Unspent Veinscore is lost
- A Dun is always gained
- Blood Marks are retained

### Fail Conditions
- Death treated as a soft fail
- Marks removed on death
- Respawn without consequence

---

## 9. The Dun Is Inert but Dangerous

### Invariants
- A Dun grants no bonuses
- A Dun cannot be removed
- A Dun adds to total Blood Marks
- Total Blood Marks drive escalation

### Fail Conditions
- Duns granting benefits
- Duns being cleansed or converted
- Systems checking only “earned” marks

---

## 10. The Hunter Is a System, Not an Enemy

### Invariants
- Hunter triggers at mark thresholds
- Hunter cannot be killed
- Hunter ignores normal combat rules
- Hunter enforces escalation, not balance

### Fail Conditions
- Hunter treated as a boss fight
- Hunter suppressed by stats or gear
- Hunter optional or ignorable

---

## 11. Enemies Obey the Same Laws

### Invariants
- Enemies use the same Interrupt rules
- Enemies obey the same damage rules
- Enemies cannot bypass cooldowns
- Enemy behavior is archetype-driven, not optimal

### Fail Conditions
- Enemies interrupting multiple times per round
- Enemies ignoring chain failure
- Enemies acting with player-only privileges

---

## 12. AI Constraints (Non-Negotiable)

### Invariants
- AI may not invent rules
- AI may not retcon state
- AI may only offer legal choices
- AI narration must follow authorized outcomes

### Fail Conditions
- AI “helpfully” bending rules
- AI skipping validation
- AI narrating impossible states

---

## 13. Design Smell Tests (Quick Checks)

If any of the following are true, stop and re-evaluate:

- Defense is always optimal
- Long chains are never attempted
- Failure feels cosmetic
- Damage feels negotiable
- The Dungeon stops escalating
- The AI feels “kind”

---

## Final Assertion

If a rule change violates **any** item in this document, it must be:
- explicitly justified,
- mechanically compensated,
- and revalidated against the entire system.

Veinbreaker works because its constraints are sharp.

Blunt them, and the game collapses into a generic action loop.

---

### END — RULES LINT
