import json
import os
from pathlib import Path
from ai.narrator import narrate
from engine.phases import allowed_actions, tick_cooldowns, list_usable_abilities
from engine.apply import apply_action
from flow.character_creation import run_character_creation
from engine.save_load import save_character, load_character
from flow.chain_declaration import prompt_chain_declaration
from engine.chain_rules import declare_chain

def load_canon():
    canon = {}
    canon_dir = Path(__file__).parent / "canon"
    for fname in os.listdir(canon_dir):
        if fname.endswith('.json'):
            with open(canon_dir / fname) as f:
                canon[fname] = json.load(f)
    abilities_path = Path(__file__).parent / "engine" / "abilities.json"
    if abilities_path.exists():
        canon["abilities.json"] = json.loads(abilities_path.read_text(encoding="utf-8"))
    return canon

def initial_state():
    return {
        'phase': {
            'current': 'out_of_combat',
            'round': 0
        },
        'party': {
            'members': [
                {
                    'id': 'pc_1',
                    'resources': {
                        'hp': 10,
                        'resolve': 3,
                        'momentum': 0,
                        'heat': 0,
                        'balance': 0
                    },
                    'chain': {
                        'active': False,
                        'declaredActions': []
                    },
                    'marks': {
                        'blood': 0,
                        'duns': 0
                    },
                    'flags': {
                        'hasInterruptedThisRound': False
                    }
                }
            ]
        },
        'enemies': [],
        'log': []
    }

def get_player_choice(allowed):
    options = allowed + ["exit"]
    print('\n--- YOUR OPTIONS ---')
    for i, a in enumerate(options):
        print(f"{i+1}. {a}")

    while True:
        choice = input('> ').strip()
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(options):
                return options[idx]
        if choice in options:
            return choice
        print('Invalid choice.')

def advance_phase(state, phase_machine, previous_phase):
    if state["phase"]["current"] != previous_phase:
        return  # action already changed phase

    transitions = phase_machine["phases"][previous_phase]["allowedTransitions"]
    if transitions:
        state["phase"]["current"] = transitions[0]


def main():
    canon = load_canon()
    phase_machine = canon['phase_machine.json']

    print("Use saved character? (y/n)")
    use_saved = input("> ").strip().lower().startswith("y")
    if use_saved:
        character = load_character()
    else:
        character = run_character_creation(
            canon,
            narrator=None  # or narrator_stub if you want flavor text
        )
        save_character(character)

    state = initial_state()
    state["party"]["members"][0].update(character)

    print('Veinbreaker AI Session Started.\n')

    while True:
        # start-of-round/turn upkeep: tick cooldowns
        tick_cooldowns(state)

        current_phase = state["phase"]["current"]
        if current_phase == "chain_declaration":
            character = state["party"]["members"][0]
            usable = list_usable_abilities(state)
            if not usable:
                print("No usable abilities available (all on cooldown).")
                state["phase"]["current"] = "chain_resolution"
                continue
            abilities = prompt_chain_declaration(character, usable)
            declare_chain(
                state,
                character,
                abilities,
                resolve_spent=0,
                stabilize=False
            )
            # set cooldowns for declared abilities
            for ability in character.get("abilities", []):
                if ability.get("name") in abilities:
                    ability["cooldown"] = ability.get("base_cooldown", 0)
            state["phase"]["current"] = "chain_resolution"
            continue

        actions = allowed_actions(state, phase_machine)
        try:
            narrate(state, actions)
        except Exception as e:
            print(f"[Narrator error: {e}]")
        choice = get_player_choice(actions)
        if choice == "exit":
            print("Exiting Veinbreaker AI session.")
            break
        prev_phase = state["phase"]["current"]
        apply_action(state, choice)
        advance_phase(state, phase_machine, prev_phase)


if __name__ == '__main__':
    main()
