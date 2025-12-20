import random
from engine.action_resolution import roll as roll_dice, resolve_defense_reaction
from engine.status import apply_status_effects
from engine.dice import roll_2d10_modified, roll_mode_for_entity


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
        atk_d20 = roll_dice("2d10")
        def_d20 = roll_dice("2d10")

        atk_total = atk_d20 + attacker.get("attack_mod", 0)
        def_total = def_d20 + defender.get("resources", {}).get("idf", 0) + defender.get("resources", {}).get("momentum", 0)

        dmg = enemy_damage_roll(attacker) if atk_total > def_total else 0

        return atk_total > def_total, dmg, {
            "atk_d20": atk_d20,
            "atk_total": atk_total,
            "def_d20": def_d20,
            "def_total": def_total
        }


def apply_interrupt(state, defender, attacker, defense_ability=None, defense_block_roll=None):
    """
    Resolve an interrupt attempt as a contested roll.

    This function is PURE:
    - No phase changes
    - No chain mutation
    - No turn control
    - No UI side-effects

    Returns:
        hit (bool)
        damage (int)
        rolls (dict)
        chain_broken (bool)
    """

    # ──────────────────────────────────────────────
    # Pull stats
    # ──────────────────────────────────────────────
    atk_stat = attacker.get("stats", {}).get("weapon", 0)
    def_stat = defender.get("stats", {}).get("defense", 0)

    atk_bonus = attacker.get("resources", {}).get("momentum", 0)
    def_bonus = defender.get("resources", {}).get("idf", 0)

    break_margin = (
        ((attacker.get("resolved_archetype") or {}).get("rhythm_profile") or {})
        .get("interrupt", {})
        .get("margin_rules", {})
        .get("break_chain_on_margin_gte")
    )
    if break_margin is None:
        break_margin = state.get("rules", {}).get("interrupt_break_margin", 5)
    break_margin = int(break_margin or 0) or 5

    # ──────────────────────────────────────────────
    # Contested roll
    # ──────────────────────────────────────────────
    atk_d20, _ = roll_2d10_modified(roll_mode_for_entity(state, attacker))
    def_d20, _ = roll_2d10_modified(roll_mode_for_entity(state, defender))

    atk_total = atk_d20 + atk_stat + atk_bonus
    def_total = def_d20 + def_stat + def_bonus

    margin = atk_total - def_total
    hit = margin >= 0

    # ──────────────────────────────────────────────
    # Damage (interrupts usually light)
    # ──────────────────────────────────────────────
    damage = 0
    if hit:
        damage = roll_dice("1d4")  # interrupt damage scale
        if defense_ability:
            summary = resolve_defense_reaction(
                state,
                defender,
                attacker,
                defense_ability,
                incoming_damage=damage,
                block_roll=defense_block_roll,
            )
            damage = int(summary.get("damage_after_block", 0) or 0)
        else:
            defender.setdefault("resources", {})
            defender["resources"]["hp"] = max(0, defender["resources"].get("hp", 0) - damage)

    # ──────────────────────────────────────────────
    # Determine chain break (RULE-LEVEL DECISION)
    # ──────────────────────────────────────────────
    chain_broken = False
    if hit and (damage > 0 or margin >= break_margin):
        chain_broken = True
        if isinstance(defender.get("chain"), dict) and defender["chain"].get("declared"):
            defender["chain"]["invalidated"] = True

    # ──────────────────────────────────────────────
    # Return ALL info to engine
    # ──────────────────────────────────────────────
    rolls = {
        "atk_d20": atk_d20,
        "def_d20": def_d20,
        "atk_total": atk_total,
        "def_total": def_total,
        "margin": margin,
    }

    return hit, damage, rolls, chain_broken

   
