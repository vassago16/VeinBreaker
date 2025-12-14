"""
Narration Manager
-----------------
Coordinates scene, combat, and aftermath narration.
Consumes engine state + logs.
Never alters game state.
"""

from typing import Dict, Any, Optional


class NarrationManager:
    def __init__(self, narrator):
        """
        narrator: VeinbreakerNarrator instance
        """
        self.narrator = narrator
        self.enabled = True

    # =========================
    # SCENE INTRO
    # =========================

    def scene_intro(
        self,
        *,
        location: str,
        environment_tags: list[str],
        enemy_presence: dict,
        player_state: dict,
        threat_level: str
    ) -> Optional[str]:
        if not self.enabled:
            return None

        payload = {
            "location": location,
            "environment_tags": environment_tags,
            "enemy_presence": enemy_presence,
            "player_state": player_state,
            "threat_level": threat_level
        }

        return self.narrator.narrate_scene(payload)

    # =========================
    # COMBAT STEP
    # =========================

    def combat_step(
        self,
        *,
        action_effects: Dict[str, Any],
        chain_index: int
    ) -> Optional[str]:
        if not self.enabled:
            return None

        payload = {
            "action": action_effects.get("ability_name"),
            "hit": action_effects.get("hit"),
            "to_hit": action_effects.get("to_hit"),
            "defense": action_effects.get("defense_roll"),
            "damage": action_effects.get("damage_applied"),
            "enemy_hp_before": action_effects.get("enemy_hp_before"),
            "enemy_hp_after": action_effects.get("enemy_hp_after"),
            "statuses_applied": action_effects.get("statuses_applied", []),
            "player_resources": {
                "resolve": action_effects.get("resolve"),
                "momentum": action_effects.get("momentum"),
                "heat": action_effects.get("heat"),
                "balance": action_effects.get("balance"),
            },
            "chain_index": chain_index,
            "chain_broken": action_effects.get("chain_broken", False),
        }

        return self.narrator.narrate(payload, scene_tag="combat")

    # =========================
    # AFTERMATH
    # =========================

    def aftermath(
        self,
        *,
        location: str,
        enemies_defeated: list[dict],
        player_state: dict,
        environment_change: str
    ) -> Optional[str]:
        if not self.enabled:
            return None

        payload = {
            "location": location,
            "enemies_defeated": enemies_defeated,
            "player_state": player_state,
            "environment_change": environment_change
        }

        return self.narrator.narrate_aftermath(payload)

    # =========================
    # CONTROL
    # =========================

    def disable(self):
        self.enabled = False

    def enable(self):
        self.enabled = True
