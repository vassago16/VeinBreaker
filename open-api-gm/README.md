# open-api-gm Overview

Quick map of the files and their roles.

## Entry & Flow
- `play.py`: Interactive loop. Loads canon data, runs character creation, calls the narrator, applies player choices, and advances phases.
- `flow/character_creation.py`: Prompts for path/abilities, builds the initial character record.

## AI Layer
- `ai/narrator.py`: Loads API key (env or `open-api-gm/apiKey`), calls OpenAI for narration, extracts text, and prints it.
- `ai/simplekeytest/testcall.py`: Basic API smoke test.

## Engine Core
- `engine/phases.py`: Defines allowed actions per phase.
- `engine/apply.py`: Applies chosen actions to state.
- `engine/character.py`: Lists available paths/abilities and builds character objects.
- `engine/validate.py` / `engine/validator.py`: Validation helpers.
- `engine/save_load.py`: Save/load character data.
- `engine/abilities.json`: Canon ability data consumed by character creation and validation.

## Canon Data (JSON)
Located in `canon/`:
- `phase_machine.json`: Phase transitions.
- `state_schema.json`: Expected state shape.
- `rules_invariants.json`: Core invariants.
- `ability_validation_rules.json`: Ability selection rules.
- `enemy_generation_rules.json`: Encounter generation knobs.
- `enemy_archetypes.json`: Enemy archetype definitions.
- `threat_budget_tables.json`: Threat budgets by tier/size.
- `rules_lint.md`: Notes/linting guidance for rules.

## Usage
Run the interactive loop (requires `OPENAI_API_KEY` env or `open-api-gm/apiKey`):
```
cd open-api-gm
python play.py
```

API key loading order: environment variable `OPENAI_API_KEY`, then `open-api-gm/apiKey` file. Narrator calls use `gpt-5-nano`.
