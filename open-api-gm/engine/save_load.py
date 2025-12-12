import json

def save_character(character, filename="character.json"):
    with open(filename, "w") as f:
        json.dump(character, f, indent=2)

def load_character(filename="character.json"):
    with open(filename) as f:
        return json.load(f)
