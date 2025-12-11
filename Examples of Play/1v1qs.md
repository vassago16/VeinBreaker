## Veinbreaker 1v1 Quick Start

Use this to get playing fast. For deeper rules, examples, and edge cases, see `VeinBreaker Player Gudie`.

### Build & Baseline
- Attributes: POW, AGI, MND, SPR start at 8; spend 18 Veinscore (no stat above 14).
- HP = 10 + POW. Pools = attribute / 2 (Martial, Shadow, Magic, Faith).
- Resolve: Max 5; regenerate 3 RP at the start of your turn; unused RP carries over up to the cap.

### Turn Start Reset
- Set Balance 0, Momentum 0, Heat 0 (unless Heat Stabilize preserved 2).
- Gain 3 RP (cap 5). Maintain any stances/buffs as their rules allow.

### Declare the Chain (before rolling)
- State every action and its target for this turn; pay RP now (minimum 1 RP per action).
- You cannot change the chain mid-sequence unless an ability says so.

### Resolve Actions (A3 Contest)
- Attack Value (AV) = d20 + modifiers + positive Balance - negative Balance.
- Defense Value (DV) = d20 + Momentum + IDF + situational mods.
- Margin 5+ can trigger Perfect Defense/Block effects. Handle enemy Interrupts as each action resolves.

### Core Rhythms Snapshot
- Balance: Boosts or penalizes accuracy based on your current stance quality.
- Heat: Builds on hits; Heat 2/3/4/5 grants +1/+2/+3/+4 damage. You can spend all Heat mid-chain to burst damage, reset Balance, or carry 2 Heat (at Heat 3+) into next turn.
- Momentum: Earned on successful Dodge/Parry/Block; adds to DV and enables Perfect Defense.

### Defense & Perfects
- Any successful defense grants Momentum.
- Perfect Defense (high margin) also gives +1 positive Balance plus any riposte/redirect your gear or ability allows.

### Primed & Execution
- A target is Primed at 3 Vulnerable, at or below 25% HP, Stagger 2, or if an effect specifies Primed.
- You may replace your next attack with Execution (cost 1 RP; automatic -2 Balance). On AV >= DV, finish them (or deal heavy damage if above 0 HP), gain 1 Blood Mark and +1 RP. On failure, the chain ends and you suffer Stagger 1.

### Win Condition & Flow
- Drop the foe to 0 HP or land Execution on a Primed target.
- Manage Balance/Heat so you can still defend against Interrupts while pushing damage.

### Quick Play Loop
1) Start turn: Reset rhythms, gain 3 RP.  
2) Declare full chain (e.g., Attack / Attack / Utility) and pay RP.  
3) Resolve actions vs DV; process Interrupts and Perfects.  
4) Track Balance, Heat, Momentum; spend Heat or declare Execution if Primed.  
5) End turn with any remaining RP carrying over (up to cap).

### Example 1v1: Two-Round Clash (See Player Guide for Full Context)
**Setup:** Martial vs Shadow. Both Tier 0, max RP 5, no stances active.  
- Martial (POW 12, HP 22) starts with Balance 0, Momentum 0, Heat 0, RP 5.  
- Shadow (AGI 12, HP 20) starts with Balance 0, Momentum 0, Heat 0, RP 5.  
Dice below use AV vs DV contests; margins >=5 can trigger Perfects.

**Round 1**
1) Martial turn start: Reset to Balance 0/Momentum 0/Heat 0, gain 3 RP (stays at cap 5).  
   - Declares chain: Attack (Pulse Strike), Attack (basic), Utility (Stonepulse Rhythm). Spends 3 RP (2 remain).  
   - Action 1 Attack: AV 15 vs DV 11 -> hit. Damage 1d4+POW (roll 3+3=6). Heat to 1. Balance to -1 (from attack). RP gain on hit: +1 (now 3).  
   - Shadow Interrupt? Skips (saves reaction).  
   - Action 2 Attack: AV 12 (14 base, -2 Balance) vs DV 12 -> contested.  
   - Shadow Interrupt? Declares Parry: DV contest 13 vs AV 12 succeeds; attack is deflected (no damage, no RP gain, Heat stays 1). Balance still shifts to -2 from the attempted strike. (No Momentum gained on a failed Parry.)  
   - Action 3 Utility (Stonepulse Rhythm): Grants +1 Attack to next Martial melee this round; Balance unchanged; RP -1 (now 3). Heat optional spend? Martial holds (Heat 1). End turn: carries 3 RP; Shadow at 14 HP after the first hit.  
2) Shadow turn start: Reset Balance 0/Momentum 0/Heat 0; gain 3 RP (to 5).  
   - Declares chain: Attack (Hemocratic strike), Utility (Wound Mark), Attack (Hemocratic strike using the Wound Mark buff). Pays 3 RP.  
   - Action 1 Attack: AV 16 vs DV (Martial) 12 -> hit. Damage 1d4+DEX (roll 2+2=4). Applies Bleed 1. Heat to 1. Balance to -1. RP +1 (now 3).  
   - Martial Interrupt? Attempts Parry: DV contest 13 vs AV 16 fails; no Momentum gained on failed Parry.  
   - Action 2 Utility (Wound Mark): Next Bleed you apply gains +1 stack. Balance steady. (RP already paid; still 3.)  
   - Action 3 Attack (Hemocratic strike; applies Bleed and gains +1 stack from Wound Mark): AV 13 (14 base, -1 Balance) vs DV 12 -> hit. Damage 1d4+DEX (roll 3+2=5). Heat to 2. Balance to -2. RP +1 (now 4). Bleed on Martial increases to **2 stacks** (Bleed 1 base +1 from Wound Mark). End turn: Shadow keeps 4 RP. Martial begins next turn with Bleed ticking for 2.

**Round 2**
1) Martial turn start: Bleed triggers (takes 2 dmg). Reset Balance 0/Momentum 0/Heat 0; gain 3 RP -> total 6 (cap 5, so 5).  
   - Declares chain: Attack (basic), Attack (Pulse Strike with +1 from prior Rhythm), Heat Burst. Pays 3 RP (2 remain).  
   - Action 1 Attack: AV 15 vs DV 12 -> hit. Damage 1d4+3+Heat bonus (Heat 0) = 5. Heat to 1. Balance to -1. RP +1 (now 3).  
   - Shadow Interrupt? Declines.  
   - Action 2 Attack (Pulse Strike, +1 to hit from Rhythm): AV 17 vs DV 12 -> hit. Damage 1d4+3=6. Heat to 2 (+1 dmg on future hits). Balance to -2. RP +1 (now 4).  
   - Martial Heat Burst (declared action 3): Spend all Heat (2) for +2 damage to the last hit (total that hit becomes 8) and reset Balance to 0. RP already paid. Heat becomes 0.  
   - End state: Shadow at low HP, Martial Balance 0, Heat 0, RP 4. Shadow still has Wound Mark primed and 4 RP for next turn.  
2) Shadow turn start: Reset Balance 0/Momentum 0/Heat 0; gain 3 RP -> 5. Bleed did not stack more yet.  
   - If Shadow survives, it can now leverage Wound Mark to apply Bleed 2 on the next hit, aiming to Prime via Stagger or Vulnerable for Execution on later rounds.

**Takeaways**
- Declare full chains up front; RP spent early creates pressure to defend.  
- Heat can be banked or burst; here it turned a solid hit into a spike while clearing Balance.  
- Perfect defenses swing Balance and Momentum—watch margin.  
- Track Primed conditions (Vulnerable 3, <=25% HP, Stagger 2) to set up Execution windows.
