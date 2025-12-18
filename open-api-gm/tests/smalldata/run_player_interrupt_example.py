"""
Simulate a simple enemy hit that gets interrupted by Feedback Shield.
Uses deterministic rolls so you can iterate on defense effects quickly.
"""
import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.stats import stat_mod


def load_ability(name):
    abilities_path = Path(__file__).parent / "abilities.json"
    data = json.loads(abilities_path.read_text(encoding="utf-8"))
    for ability in data.get("abilities", []):
        if ability.get("name") == name:
            return deepcopy(ability)
    raise KeyError(f"Ability not found: {name}")


def apply_feedback_shield(character, enemy, incoming_damage, shield_roll, ability):
    """
    Minimal Feedback Shield resolution:
    - Reduce incoming damage by shield_roll (1d6 in data, we force a value for reproducibility).
    - If reduced to 0, reflect INT damage to attacker.
    - Gain +1 momentum.
    Returns a dict summary.
    """
    reduced = max(0, incoming_damage - shield_roll)
    reflected = 0
    if reduced == 0:
        reflected = max(0, stat_mod(character["stats"].get("INT", 10)))
        enemy["hp"] = enemy.get("hp", 0) - reflected
    character["resources"]["momentum"] = character["resources"].get("momentum", 0) + 1
    character["resources"]["hp"] = character["resources"].get("hp", 0) - reduced
    return {
        "incoming": incoming_damage,
        "shield_roll": shield_roll,
        "damage_after_shield": reduced,
        "reflected_damage": reflected,
    }


def main():
    feedback = load_ability("Feedback Shield")

    character = {
        "name": "Test PC",
        "stats": {"INT": 14},
        "resources": {"hp": 12, "momentum": 0},
    }
    enemy = {
        "name": "Training Dummy",
        "hp": 15,
    }

    incoming_damage = 8  # enemy hit for 8
    shield_roll = 5      # force a 1d6=5 reduction for determinism

    print(f"=== Player Interrupt: {feedback['name']} ===")
    print(f"Enemy hits for {incoming_damage} damage.")
    print(f"Player interrupts with {feedback['name']} (forced shield roll={shield_roll}).")

    result = apply_feedback_shield(character, enemy, incoming_damage, shield_roll, feedback)

    print(f"Damage reduced to {result['damage_after_shield']} (blocked {result['incoming'] - result['damage_after_shield']}).")
    print(f"Player HP: {character['resources']['hp']} | Momentum: {character['resources']['momentum']}")
    if result["reflected_damage"]:
        print(f"Reflected {result['reflected_damage']} damage to {enemy['name']} (enemy HP now {enemy['hp']}).")
    else:
        print(f"No reflection (damage not fully negated). Enemy HP remains {enemy['hp']}.")
    print("=== End ===")


if __name__ == "__main__":
    main()
