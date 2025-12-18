Entry points:

Game.step (web wrapper) → play.game_step(ctx, player_input)
/step API → GameSession.step → Game.handle_input → Game.step → game_step
game_step orchestrates:

Resolves any state["awaiting"] with incoming player_input
Runs start-of-round round_upkeep(state) when entering chain_declaration
Dispatches by phase:
chain_declaration → handle_chain_declaration
chain_resolution → handle_chain_resolution
Falls through to action handling, narration, etc., after those return
Phase handlers:

handle_chain_declaration
Blocking (CLI): prompt chain, call declare_chain, set cooldowns, advance to chain_resolution
Non-blocking (web): emit declare_chain via emit_declare_chain, set state["awaiting"]={"type":"chain_builder",...}, or process submitted action:"declare_chain"
handle_chain_resolution
Resolves the declared chain: rolls, applies effects, emits character_update, interrupts, enemy turn, loot/aftermath, phase transitions
Uses emit_action_narration for narration plumbing
Emits combat_state, character_update, interrupt events as needed
Event emitters (UI-agnostic) in ui/events.py:

emit_event probes ui.provider.session.emit
Helpers/builders: emit_combat_state/build_combat_state, emit_combat_log, emit_interrupt, emit_character_update/build_character_update, emit_declare_chain/build_declare_chain
State helpers:

round_upkeep (resolve regen, reset momentum/balance/heat, cooldowns)
usable_ability_objects, emit_action_narration, enemy chain/resolution helpers, damage reduction, etc.
Awaiting/input rules (web):

UI never returns input directly; choices/chain builder set state["awaiting"]
game_step consumes player_input keys (choice, action, chain) to resolve awaited state
declare_chain action maps submitted IDs/names to abilities, calls declare_chain, advances to chain_resolution
API/UI plumbing:

/step drives the game; /events drains buffered events to the web UI
Frontend polls /events, handles events (declare_chain, character_update, combat_state, interrupt, etc.)
/emit exists for out-of-band events into a session
Character data:

/character returns normalized default character (from disk or fallback)
create_game_context (in play.py) seeds state; web skips blocking character creation
Narration:

emit_action_narration bridges action log → narrator (NARRATION/NARRATOR) → ui.narration, with logging/error handling
Combat resolution calls this per action; loot/aftermath hooks likewise emit narration if enabled