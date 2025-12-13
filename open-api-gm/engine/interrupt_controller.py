import random
from engine.action_resolution import roll as roll_dice


def enemy_damage_roll(enemy):
    """
    Compute enemy damage using stat_block.damage_profile if present.
    Fallback to 1d6.
    """
    profile = enemy.get("stat_block", {}).get("damage_profile", {}) if enemy else {}
    dmg = profile.get("baseline") or {}
    dice = dmg.get("dice", "1d6")
    flat = dmg.get("flat", 0)
    return roll_dice(dice) + flat


class InterruptController:
    def __init__(self, enemy):
        """
        enemy: dict with at least attack_mod (int), id (str optional)
        """
        self.enemy = enemy or {}

    def should_interrupt(self, state, action_index):
        """
        Decide if enemy attempts an interrupt at a given action index.
        TODO: plug in rhythm/archetype logic from the wiki.
        """
        # Stub: try to interrupt on action 2+
        return action_index >= 1

    def roll_interrupt(self, attacker, defender):
        """
        attacker: enemy dict (with attack_mod)
        defender: player dict with resources: idf, momentum, hp
        Returns (hit, dmg, rolls)
        """
        atk_d20 = random.randint(1, 20)
        def_d20 = random.randint(1, 20)

        atk_total = atk_d20 + attacker.get("attack_mod", 0)
        def_total = def_d20 + defender.get("resources", {}).get("idf", 0) + defender.get("resources", {}).get("momentum", 0)

        dmg = enemy_damage_roll(attacker) if atk_total > def_total else 0

        return atk_total > def_total, dmg, {
            "atk_d20": atk_d20,
            "atk_total": atk_total,
            "def_d20": def_d20,
            "def_total": def_total
        }


def apply_interrupt(state, character, enemy):
    """
    Attempts an interrupt; if damage > 0, break the chain.
    """
    ic = InterruptController(enemy)
    hit, dmg, rolls = ic.roll_interrupt(enemy or {}, character or {})
    margin = rolls["atk_total"] - rolls["def_total"]
    if hit and dmg > 0:
        # apply damage and break chain
        character["resources"]["hp"] = max(0, character["resources"].get("hp", 0) - dmg)
    if hit and margin >= 5:
        # invalidate chain even if damage was 0
        if character.get("chain", {}).get("declared"):
            character["chain"]["invalidated"] = True
            character["chain"]["declared"] = False
            character["chain"]["abilities"] = []
            character["chain"]["reason"] = "interrupted"
    return hit, dmg, rolls
