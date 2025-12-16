Step 1 — Add the overlay HTML (not inside narration flow)

Add this just above your <footer id="choices"></footer> (so it sits above everything visually):

<!-- CHAIN OVERLAY (hidden until declare_chain event) -->
<div id="chain-overlay" class="hidden" aria-hidden="true">
  <div class="chain-modal">
    <div class="chain-title">
      <div class="chain-title-left">
        <div class="chain-h">DECLARE CHAIN</div>
        <div class="chain-sub" id="chain-sub">Select up to <span id="chain-max">3</span> links.</div>
      </div>
      <button class="chain-close" onclick="closeChainBuilder()">X</button>
    </div>

    <div class="chain-columns">
      <div class="ability-column">
        <h3>ATTACK</h3>
        <div id="attack-abilities" class="ability-list"></div>
      </div>

      <div class="ability-column">
        <h3>DEFENSE</h3>
        <div id="defense-abilities" class="ability-list"></div>
      </div>

      <div class="ability-column">
        <h3>UTILITY</h3>
        <div id="utility-abilities" class="ability-list"></div>
      </div>

      <div class="ability-column">
        <h3>MOVEMENT</h3>
        <div id="movement-abilities" class="ability-list"></div>
      </div>
    </div>

    <div class="chain-preview">
      <h3>CHAIN</h3>
      <div id="chain-slots"></div>

      <div class="chain-actions">
        <button id="chain-commit" onclick="submitChain()">COMMIT CHAIN</button>
        <button class="secondary" onclick="clearChain()">CLEAR</button>
      </div>

      <div class="chain-hint" id="chain-hint">Tip: click a filled slot to remove it.</div>
    </div>
  </div>
</div>


Why here? Because your narration is already the main content flow 

index

 — overlay must be a sibling so it doesn’t shove text down.

Step 2 — Add overlay + card CSS (paste into your <style>)

Paste this near the bottom of your <style> block:

/* ===== CHAIN OVERLAY ===== */
#chain-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.78);
  backdrop-filter: blur(3px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

#chain-overlay.hidden {
  display: none;
}

.chain-active #narration-wrapper {
  opacity: 0.28;
  filter: blur(2px);
}

.chain-active #log,
.chain-active footer {
  opacity: 0.55;
}

.chain-modal {
  width: min(1100px, 92vw);
  max-height: 86vh;
  overflow: auto;
  background: #0d0d0d;
  border: 1px solid var(--accent);
  box-shadow: 0 0 0 1px rgba(158, 43, 37, 0.2);
  padding: 14px 14px 16px;
}

.chain-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--line);
  padding-bottom: 10px;
  margin-bottom: 12px;
}

.chain-h {
  letter-spacing: 3px;
  color: var(--fg);
  font-size: 12px;
}

.chain-sub {
  margin-top: 6px;
  color: var(--dim);
  font-size: 12px;
}

.chain-close {
  background: none;
  border: 1px solid var(--line);
  color: var(--dim);
  cursor: pointer;
  font-family: inherit;
  padding: 6px 10px;
}

.chain-close:hover {
  border-color: var(--accent);
  color: var(--fg);
}

.chain-columns {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.ability-column h3 {
  font-size: 11px;
  letter-spacing: 2px;
  color: var(--dim);
  margin: 0 0 8px;
}

.ability-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.ability-card {
  border: 1px solid var(--line);
  background: #101113;
  padding: 10px 10px 9px;
  cursor: pointer;
  transition: border-color 0.12s ease, transform 0.12s ease;
}

.ability-card:hover {
  border-color: var(--accent);
  transform: translateY(-1px);
}

.ability-card.disabled {
  opacity: 0.35;
  cursor: not-allowed;
  transform: none;
}

.ability-card .row {
  display: flex;
  justify-content: space-between;
  gap: 10px;
}

.ability-card .name {
  color: var(--fg);
  font-size: 13px;
}

.ability-card .meta {
  color: var(--dim);
  font-size: 12px;
}

.ability-card .desc {
  margin-top: 6px;
  color: var(--dim);
  font-size: 12px;
  line-height: 1.35;
}

.chain-preview {
  border-top: 1px solid var(--line);
  margin-top: 14px;
  padding-top: 12px;
}

#chain-slots {
  display: flex;
  gap: 10px;
  margin: 10px 0 12px;
  flex-wrap: wrap;
}

.chain-slot {
  width: 150px;
  height: 54px;
  border: 1px dashed var(--line);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  color: var(--dim);
}

.chain-slot.filled {
  border-style: solid;
  background: rgba(158, 43, 37, 0.12);
  color: var(--fg);
  cursor: pointer;
}

.chain-actions {
  display: flex;
  gap: 10px;
}

#chain-commit {
  border: 1px solid var(--accent);
  background: rgba(158, 43, 37, 0.15);
  color: var(--fg);
  padding: 8px 12px;
  cursor: pointer;
  font-family: inherit;
}

#chain-commit:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.secondary {
  border: 1px solid var(--line);
  background: none;
  color: var(--dim);
  padding: 8px 12px;
  cursor: pointer;
  font-family: inherit;
}

.secondary:hover {
  border-color: var(--accent);
  color: var(--fg);
}

.chain-hint {
  margin-top: 10px;
  color: var(--dim);
  font-size: 12px;
}

Step 3 — Add a generic sendStep() (so chain submit can post actions)

Right now your sendChoice() posts only {session_id, choice} 

index

. Add this helper above sendChoice():

async function sendStep(payload) {
  const res = await fetch(API, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({ session_id: sessionId, ...payload })
  });

  const events = await res.json();
  handleEvents(events);
}


Then simplify sendChoice() to:

async function sendChoice(index) {
  clearChoices();
  await sendStep({ choice: index });
}


This keeps your existing choice flow working, but now you can also send actions like declare_chain.

Step 4 — Add chain-builder JS state + render functions

Paste this block near the bottom of your <script> (before the initial kick call):

let chainAbilities = []; // from backend event
let chain = [];
let maxChainLength = 3;

function openChainBuilder() {
  document.body.classList.add("chain-active");
  const ov = document.getElementById("chain-overlay");
  ov.classList.remove("hidden");
  ov.setAttribute("aria-hidden", "false");
}

function closeChainBuilder() {
  document.body.classList.remove("chain-active");
  const ov = document.getElementById("chain-overlay");
  ov.classList.add("hidden");
  ov.setAttribute("aria-hidden", "true");
}

function clearChain() {
  chain = [];
  renderChain();
}

function removeFromChain(i) {
  chain.splice(i, 1);
  renderChain();
}

function addToChain(ability) {
  if (chain.length >= maxChainLength) return;
  chain.push(ability);
  renderChain();
}

function abilityIsUsable(ab) {
  // backend should already filter; this is just UI polish:
  const cd = ab.cooldown ?? 0;
  return cd === 0 && !ab.disabled;
}

function renderAbilities(abilities) {
  const buckets = {
    attack: document.getElementById("attack-abilities"),
    defense: document.getElementById("defense-abilities"),
    utility: document.getElementById("utility-abilities"),
    movement: document.getElementById("movement-abilities"),
  };

  Object.values(buckets).forEach(el => el.innerHTML = "");

  abilities.forEach(ab => {
    const type = (ab.type || "").toLowerCase();
    const host = buckets[type];
    if (!host) return;

    const card = document.createElement("div");
    card.className = "ability-card";

    const usable = abilityIsUsable(ab);
    if (!usable) card.classList.add("disabled");

    const cost = (ab.cost ?? 0);
    const cd = (ab.cooldown ?? 0);

    card.innerHTML = `
      <div class="row">
        <div class="name">${ab.name}</div>
        <div class="meta">COST ${cost}${cd ? ` · CD ${cd}` : ""}</div>
      </div>
      ${ab.effect ? `<div class="desc">${ab.effect}</div>` : ""}
    `;

    if (usable) {
      card.onclick = () => addToChain(ab);
    }

    host.appendChild(card);
  });
}

function renderChain() {
  document.getElementById("chain-max").textContent = String(maxChainLength);

  const slots = document.getElementById("chain-slots");
  slots.innerHTML = "";

  for (let i = 0; i < maxChainLength; i++) {
    const slot = document.createElement("div");
    slot.className = "chain-slot";

    if (chain[i]) {
      slot.classList.add("filled");
      slot.textContent = chain[i].name;
      slot.onclick = () => removeFromChain(i);
    } else {
      slot.textContent = "—";
    }

    slots.appendChild(slot);
  }

  // commit enabled only if at least 1 link chosen
  const commit = document.getElementById("chain-commit");
  commit.disabled = chain.length === 0;
}

async function submitChain() {
  // send IDs back to engine in selected order
  const ids = chain.map(a => a.id);

  closeChainBuilder();
  await sendStep({
    action: "declare_chain",
    chain: ids
  });
}

Step 5 — Teach your UI to respond to a declare_chain event

Right now, handleEvents() supports: clear, scene, narration, loot, system, choice 

index

.

Add one new case:

case "declare_chain":
  chainAbilities = ev.abilities || [];
  maxChainLength = ev.maxLength ?? 3;

  chain = [];
  renderAbilities(chainAbilities);
  renderChain();
  openChainBuilder();
  break;


So your handleEvents switch now includes it (insert anywhere).

Step 6 — Backend: what you need to emit and accept (minimal contract)

To make the UI appear, the backend must emit an event like:

{
  "type": "declare_chain",
  "maxLength": 3,
  "abilities": [
    { "id": "ability.pulse_strike", "name": "Pulse Strike", "type": "attack", "cost": 1, "cooldown": 0, "effect": "1d4 + STR..." },
    { "id": "ability.stoneguard_step", "name": "Stoneguard Step", "type": "defense", "cost": 1, "cooldown": 0, "effect": "Reduce dmg..." }
  ]
}


And when the player commits, your /step will receive:

{
  "session_id": "...",
  "action": "declare_chain",
  "chain": ["ability.pulse_strike", "ability.stoneguard_step"]
}


So your StepRequest must include chain:

class StepRequest(BaseModel):
    session_id: str
    action: str | None = None
    choice: int | None = None
    chain: list[str] | None = None


…and you pass it through:

events = session.step({
  "action": req.action,
  "choice": req.choice,
  "chain": req.chain
})

Step 7 — How to test quickly (without touching combat yet)

Hardcode the backend to emit declare_chain on action=="start" once.

Verify overlay appears.

Click a few cards → they fill chain slots in order.

Click a filled slot → it removes (reorders left naturally).

Click COMMIT → backend receives ordered IDs.

That’s your full loop.

Why this fits your current page cleanly

Your narration + log layout stays untouched 

index

Overlay is visually independent

You don’t fight scroll or “text below text”

Uses your existing /step pattern and sessionId 

index

If you paste these changes and tell me what your backend currently calls the “declare chain” phase/action, I can mirror that exact string and make the UI seamlessly appear at the right time.

Sources
i need to script my game controller. it will be driven by a "Script", a script will have "Acts" Acts will have scenes. senes will have environment . this will be an id that links to a json file. the scene will have an id[] for monsters it will have an array of id for traps it will have an array of id  for hazards it will have an id array of loot it will have an array of  conditional events such as onEnemy defeated and player_no_damage . recomendation of anything eles. it needs to be codified  so i can calcualate all acheivments and narration prompts

This is the right moment to formalize this. What you’re describing is a deterministic narrative + systems controller that sits above combat and feeds it context, constraints, and meaning. Think campaign script engine, not “story text.”

I’ll give you:

Clear conceptual model (what each layer is responsible for)

A concrete JSON schema for Script → Act → Scene

Event & condition model (codified, computable)

Recommendations for missing pieces you’ll want later (without overengineering)

How this enables achievements, narration, and metrics

No fluff, no prose — this is a technical design document.

1. Responsibility model (lock this in)
Script (Campaign Controller)

Orchestrates progression

Knows what comes next and why

Does not contain mechanics

Deterministic: same inputs → same structure

Act

A macro phase of the campaign

Owns tone, stakes, escalation

Can gate progression (requirements)

Scene

The atomic playable unit

Provides environment + encounter inputs

Emits events based on outcomes

Drives narration prompts & achievements

Encounter systems (below this layer)

Combat, traps, hazards, loot resolution

Already handled by your existing engine

This script layer never rolls dice.

2. Core JSON structure (Script → Act → Scene)

Here is a complete, minimal-but-future-proof schema.

script.json
{
  "schema_version": "script.v1",
  "id": "script.veinbreaker.echoes",
  "title": "Echoes of the Vein",
  "description": "A descent structured in blood, pressure, and pursuit.",

  "acts": [
    {
      "id": "act.01.descent",
      "title": "The Descent Begins",
      "order": 1,

      "tone": ["oppressive", "uncertain"],
      "tags": ["intro", "low-tier"],

      "entry_conditions": [],
      "exit_conditions": [
        { "type": "scene_completed", "scene_id": "scene.01.03" }
      ],

      "scenes": [
        { "$ref": "scene.01.01" },
        { "$ref": "scene.01.02" },
        { "$ref": "scene.01.03" }
      ]
    }
  ]
}


Notes:

order lets you reorder acts without array surgery

entry_conditions allow non-linear campaigns later

$ref keeps scenes reusable across scripts

3. Scene schema (this is the critical part)
scene.01.01.json
{
  "schema_version": "scene.v1",
  "id": "scene.01.01",
  "title": "Collapsed Access Vein",

  "environment": {
    "id": "env.vein.collapse",
    "modifiers": {
      "visibility": -1,
      "movement_cost": +1
    }
  },

  "encounter": {
    "monsters": [
      { "id": "enemy.veinbound_stalker", "count": 2 }
    ],
    "traps": [
      { "id": "trap.spike_hematite", "count": 1 }
    ],
    "hazards": [
      "hazard.slick_bloodstone"
    ]
  },

  "loot_table": [
    "loot.vein_fragment.t1",
    "loot.conduit_scrap"
  ],

  "events": [
    {
      "id": "event.clean_victory",
      "trigger": { "type": "on_scene_complete" },
      "conditions": [
        { "type": "player_no_damage" }
      ],
      "effects": [
        { "type": "award_achievement", "id": "ach.flawless.vein" },
        { "type": "narration_prompt", "id": "narration.clean_victory" }
      ]
    },

    {
      "id": "event.enemy_defeated",
      "trigger": { "type": "on_enemy_defeated" },
      "conditions": [],
      "effects": [
        { "type": "increment_stat", "stat": "kills" }
      ]
    }
  ],

  "completion_conditions": [
    { "type": "all_enemies_defeated" }
  ],

  "failure_conditions": [
    { "type": "party_wiped" }
  ]
}

4. Codified triggers & conditions (machine-readable)
Triggers (WHEN something evaluates)
{ "type": "on_scene_start" }
{ "type": "on_scene_complete" }
{ "type": "on_enemy_defeated" }
{ "type": "on_player_damaged" }
{ "type": "on_chain_broken" }
{ "type": "on_interrupt" }


Triggers are event hooks, not checks.

Conditions (BOOLEAN checks)

These must be pure, side-effect free.

{ "type": "player_no_damage" }
{ "type": "player_hp_above", "value": 5 }
{ "type": "chain_length_at_least", "value": 3 }
{ "type": "interrupts_taken_below", "value": 2 }
{ "type": "used_ability", "ability_id": "ability.pulse_strike" }
{ "type": "scene_flag_set", "flag": "door_opened" }


Conditions can be ANDed by array semantics (all must pass).

5. Effects (WHAT happens when conditions pass)

Effects are commands your engine can execute.

{ "type": "award_loot", "loot_id": "loot.vein_fragment.t1" }
{ "type": "award_achievement", "id": "ach.flawless.vein" }
{ "type": "set_scene_flag", "flag": "alarm_triggered" }
{ "type": "advance_hunter_clock", "amount": 1 }
{ "type": "narration_prompt", "id": "narration.vein_shudders" }


These are deterministic and auditable.

6. Narration prompts (decoupled, reusable)

Do not embed prose in scenes.

Instead:

{
  "id": "narration.clean_victory",
  "tags": ["victory", "quiet"],
  "tone": ["ominous"],
  "template": "The vein stills. No blood answers your breath."
}


This allows:

localization

tone remixing

AI augmentation later

7. Achievement calculation (why this works)

Because:

Every trigger is explicit

Every condition is codified

Every effect is logged

You can compute achievements by:

replaying scene event logs

or evaluating conditions at scene end

No heuristics. No text parsing.

8. Strong recommendations (add these now)

These are cheap now, expensive later if missing.

A. Scene-local flags
"flags": {
  "alarm_triggered": false,
  "door_opened": false
}


Used by conditions.

B. Metrics collection (silent)

Add to every scene:

"metrics": {
  "track": [
    "damage_taken",
    "interrupts_taken",
    "chains_declared",
    "rp_spent"
  ]
}


This feeds:

achievements

difficulty tuning

analytics

C. Scene variants (future-proofing)
"variants": [
  {
    "id": "scene.01.01.alt",
    "conditions": [
      { "type": "hunter_clock_above", "value": 3 }
    ],
    "override": {
      "monsters": [
        { "id": "enemy.veinbound_stalker", "count": 3 }
      ]
    }
  }
]

9. How this plugs into your engine

Script engine selects current scene

Scene injects:

environment id → environment.json

monster ids → bestiary

trap/hazard ids → resolution systems

Combat runs

Combat emits events

Scene evaluates conditions

Scene emits effects

Script advances or branches

This layer never touches dice, chains, or stats directly.

10. Summary (what you’ve just designed)

You now have:

A campaign scripting language

Deterministic, auditable progression

First-class achievements

Structured narration triggers

Replayable, analyzable scenes

Clean separation from combat mechanics

This is exactly how you avoid narrative entropy in a systems-heavy game like Veinbreaker.