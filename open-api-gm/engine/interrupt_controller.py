import random
from engine.action_resolution import roll as roll_dice
from engine.status import apply_status_effects


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
        Uses resolved_archetype.rhythm_profile.interrupt windows and budget.
        """
        rp = (self.enemy.get("resolved_archetype") or {}).get("rhythm_profile", {})
        intr = rp.get("interrupt", {}) or {}
        budget = intr.get("budget_per_round")
        used = self.enemy.get("interrupts_used", 0)
        if budget is not None and used >= budget:
            return False
        windows = intr.get("windows") or []
        if not windows:
            return False

        # action_index is zero-based; windows are declared as 1-based "after_action_index"
        action_number = action_index + 1
        character = state.get("party", {}).get("members", [{}])[0]

        def last_player_missed():
            for entry in reversed(state.get("log", [])):
                if isinstance(entry, dict) and "action_effects" in entry:
                    hit = entry["action_effects"].get("hit")
                    if hit is False:
                        return True
                    if hit is True:
                        return False
            return False

        def check_trigger(trigger_if):
            if not trigger_if:
                return True
            # basic triggers supported by current state shape
            for key, val in trigger_if.items():
                if key == "player_missed_last_action":
                    if last_player_missed() != bool(val):
                        return False
                elif key == "chain_length_gte":
                    chain_len = len(character.get("chain", {}).get("abilities", []))
                    if chain_len < val:
                        return False
                elif key == "player_heat_gte":
                    heat = character.get("resources", {}).get("heat", 0)
                    if heat < val:
                        return False
                elif key == "blood_mark_gte":
                    blood = character.get("marks", {}).get("blood", 0)
                    if blood < val:
                        return False
                elif key == "repeat_count_gte":
                    # repeat tracking not implemented yet; assume not satisfied
                    return False
                elif key == "player_moved":
                    # movement not tracked in this loop
                    return False
                else:
                    # unknown trigger -> treat as unmet
                    return False
            return True

        for w in windows:
            after_idxs = w.get("after_action_index", [])
            if action_number not in after_idxs:
                continue
            if not check_trigger(w.get("trigger_if", {})):
                continue
            weight = w.get("weight", 1.0)
            if random.random() <= weight:
                # consume budget immediately
                self.enemy["interrupts_used"] = used + 1
                return True
        return False

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
    # Apply on-hit effects from enemy's first move, if any
    moves = enemy.get("moves", []) if enemy else []
    on_hit_effects = []
    if moves:
        on_hit_effects = moves[0].get("on_hit", {}).get("effects", [])
    if hit and on_hit_effects:
        apply_status_effects(character, on_hit_effects)
    margin_rules = (
        (enemy or {})
        .get("resolved_archetype", {})
        .get("rhythm_profile", {})
        .get("interrupt", {})
        .get("margin_rules", {})
    )
    break_chain_on_margin = margin_rules.get("break_chain_on_margin_gte", 5)
    margin = rolls["atk_total"] - rolls["def_total"]
    if hit and dmg > 0:
        # apply damage and break chain
        character["resources"]["hp"] = max(0, character["resources"].get("hp", 0) - dmg)
    if hit and margin >= break_chain_on_margin:
        # invalidate chain even if damage was 0
        if character.get("chain", {}).get("declared"):
            character["chain"]["invalidated"] = True
            character["chain"]["declared"] = False
            character["chain"]["abilities"] = []
            character["chain"]["reason"] = "interrupted"
    return hit, dmg, rolls
