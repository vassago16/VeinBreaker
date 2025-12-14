import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.action_resolution import resolve_action_step, apply_action_effects, check_exposure

def load_ability(abilities, name):
    for a in abilities["abilities"]:
        if a.get("name") == name:
            return deepcopy(a)
    raise KeyError(f"Ability not found: {name}")

def main():
    with open("abilities.json", "r", encoding="utf-8") as f:
        abilities = json.load(f)
    with open("encounter_example_01.json", "r", encoding="utf-8") as f:
        enc = json.load(f)

    state = {"log": [], "pending_action": None}

    character = enc["player"]
    enemy = enc["enemy"]["instance"]
    enemies = [enemy]

    chain = enc["scripted_chain"]["abilities"]
    rolls = enc["scripted_chain"]["fixed_attack_d20"]

    print(f"=== {enc['title']} ===")
    print(f"Enemy: {enemy['name']} (HP {enemy['hp']}, DV {enemy['stat_block']['defense']['dv_base']})")
    print(f"Player: {character['name']} (Resolve {character['resources']['resolve']}, Heat {character['resources']['heat']}, Balance {character['resources']['balance']})")
    print()

    for idx, (ability_name, d20) in enumerate(zip(chain, rolls), start=1):
        ability = load_ability(abilities, ability_name)

        print(f"-- Action {idx}: {ability_name} (forced d20={d20}) --")
        resolve_action_step(state, character, ability, attack_roll=d20)
        apply_action_effects(state, character, enemies)

        exposure = check_exposure(character)

        last = state["log"][-1]["action_effects"]
        print(f"to_hit={last.get('to_hit')} vs defense_roll={last.get('defense_roll')} => {'HIT' if last.get('hit') else 'MISS'}")
        if last.get("hit"):
            print(f"damage_applied={last.get('damage_applied')} (heat_bonus={last.get('heat_bonus')})")
        if last.get("statuses_applied"):
            print(f"statuses_applied={last.get('statuses_applied')}")
        print(f"player: resolve={last.get('resolve')} momentum={last.get('momentum')} heat={last.get('heat')} balance={last.get('balance')}")
        print(f"enemy: hp={enemy.get('hp')} momentum={enemy.get('momentum',0)}")
        if exposure:
            print(f"EXPOSURE: {exposure}")
        print()

        if enemy.get("hp", 0) <= 0:
            print("Enemy defeated.")
            break

    print("=== End ===")

if __name__ == "__main__":
    main()
