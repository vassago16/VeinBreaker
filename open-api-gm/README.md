# open-api-gm Overview

Quick map of the files and their roles.

## Source Of Truth (Runtime Loads)
- Rules/config: `open-api-gm/canon/`
- Game content: `open-api-gm/game-data/` (monsters, abilities, scenes, loot, traps, hazards, statuses)
- Player data: `open-api-gm/characters/` (profiles) + `open-api-gm/player_state.json` (mutable runtime/save state)

Everything outside those folders (e.g. `monster-maker/`, `Player Guide/`, `Path-maker/`, `trading-card-maker/`) is authoring/reference tooling and is not loaded by the runtime.

## Entry & Flow
- `play.py`: Core game logic. Builds initial state, runs character creation (CLI), advances phases, resolves chains. Exposes non-blocking emitters for the web UI.
- `game_runner.py`: Thin wrapper that constructs a `Game` with a UI provider and forwards step-based input.
- `game_session.py`: Holds a session’s event buffer and forwards inputs to the game.
- `flow/character_creation.py`: Prompts for path/abilities, builds the initial character record (blocking/CLI).

## AI Layer
- `ai/narrator.py`: Loads API key (env or `open-api-gm/apiKey`), calls OpenAI for narration, extracts text, and prints it.
- `ai/simplekeytest/testcall.py`: Basic API smoke test.

## Engine Core
- `engine/phases.py`: Defines allowed actions per phase.
- `engine/apply.py`: Applies chosen actions to state.
- `engine/character.py`: Lists available paths/abilities and builds character objects.
- `engine/validate.py` / `engine/validator.py`: Validation helpers.
- `engine/save_load.py`: Save/load character data.
- `game-data/abilities.json`: Canon ability data consumed by character creation and validation.
- `ui/events.py`: Shared event emitters/builders for non-blocking UIs.
- `ui/web_provider.py` / `ui/cli_provider.py`: UI adapters for web vs. CLI.
- `index.html`: Web client (polls `/events`, renders narration/log/chain builder/character HUD).

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
### Web (step-based, non-blocking)
- Start the API server (FastAPI + uvicorn):
  ```
  cd open-api-gm
  uvicorn server:app --reload --host 0.0.0.0 --port 8000
  ```
- Open `index.html` in a browser (or run your local web runner). The client polls `/events` and posts to `/step`.
- Endpoints:
  - `POST /step` — advance the game with `{session_id, action?, choice?, chain?}`.
  - `POST /events` — drain buffered events for a session.
  - `POST /emit` — push an arbitrary event payload into a session (testing).
  - `GET /character` — fetch the current/default character payload.

### CLI (blocking)
- Requires `OPENAI_API_KEY` env or `open-api-gm/apiKey` file.
- Run:
  ```
  cd open-api-gm
  python play.py
  ```

API key loading order: environment variable `OPENAI_API_KEY`, then `open-api-gm/apiKey` file. Narrator calls use `gpt-5-nano`.
