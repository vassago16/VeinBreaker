from typing import Any, Callable, Dict

from ui.events import emit_declare_chain


class Combat:
    """
    Thin combat orchestrator for non-blocking UIs.
    Delegates resolution to injected handlers but owns prompting/awaiting.
    """

    def __init__(
        self,
        ctx: Dict[str, Any],
        handle_chain_declaration: Callable[[Dict[str, Any], Dict[str, Any]], Any],
        handle_chain_resolution: Callable[[Dict[str, Any]], Any],
        usable_abilities_fn: Callable[[Dict[str, Any]], list],
    ):
        self.ctx = ctx
        self.handle_chain_declaration = handle_chain_declaration
        self.handle_chain_resolution = handle_chain_resolution
        self.usable_abilities_fn = usable_abilities_fn

    def start(self):
        state = self.ctx["state"]
        ui = self.ctx["ui"]
        state["active_combatant"] = "player"
        state["phase"]["current"] = "chain_declaration"
        state["phase"]["round_started"] = False
        state.pop("awaiting", None)
        # For non-blocking UI, immediately surface the builder prompt.
        if not getattr(ui, "is_blocking", True):
            usable = self.usable_abilities_fn(state)
            ui.choice("Build your next chain?", ["Build chain"])
            emit_declare_chain(ui, usable, max_len=state.get("phase", {}).get("chain_max", 6) or 6)
            state["awaiting"] = {"type": "chain_builder", "options": usable}

    def step(self, player_input: Dict[str, Any]):
        state = self.ctx["state"]
        if state["phase"]["current"] == "chain_declaration":
            return self.handle_chain_declaration(self.ctx, player_input)
        if state["phase"]["current"] == "chain_resolution":
            return self.handle_chain_resolution(self.ctx)
        return None
