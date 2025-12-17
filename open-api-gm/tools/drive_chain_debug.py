"""
Deterministic harness to drive chain declaration + combat resolution and let you debug/step through.

Usage (plain run):
  python tools/drive_chain_debug.py

Usage (step through with pdb):
  python -m pdb tools/drive_chain_debug.py

It:
  - builds a game context (no narration)
  - generates + enters an encounter
  - declares a one-link chain ("Basic Strike")
  - ticks once to resolve the chain

You can set breakpoints in VS Code or use pdb to step through `game_step`, `resolve_chain`, etc.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, List

# Ensure project root on sys.path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from play import create_game_context, start_game, game_step  # noqa: E402
from ui.ui import UI  # noqa: E402
from ui.provider import UIProvider  # noqa: E402


class HarnessProvider(UIProvider):
    """Non-interactive provider that auto-picks the first option."""

    is_blocking = True

    def scene(self, text: str, data: Any = None):
        print(f"[SCENE] {text[:120]}...")

    def narration(self, text: str, data: Any = None):
        print(f"[NARRATION] {text}")

    def system(self, text: str, data: Any = None):
        print(f"[SYSTEM] {text}")

    def error(self, text: str, data: Any = None):
        print(f"[ERROR] {text}")

    def choice(self, prompt: str, options: List[str], data: Any = None):
        print(f"[CHOICE] {prompt} -> picking 0 ({options[0]})")
        return 0

    def clear(self, target: str = "narration"):
        pass

    def text_input(self, prompt: str):
        print(f"[TEXT INPUT] {prompt} -> returning empty string")
        return ""

    def loot(self, text: str, data: Any = None):
        print(f"[LOOT] {text}")


def inject_rolls(sequence: List[int]):
    """Monkeypatch engine.action_resolution.roll to use a deterministic sequence."""
    import engine.action_resolution as ar  # type: ignore

    rolls = list(sequence)

    def _roll(_dice: str) -> int:
        if not rolls:
            raise RuntimeError("Out of predefined rolls")
        return rolls.pop(0)

    ar.roll = _roll


def main():
    # Optional deterministic rolls (attacker/defender alternating)
    roll_sequence = [
        16, 15,
        9, 18,
        17, 12,
        4, 8,
        3, 14,
        1, 6,
    ]
    inject_rolls(roll_sequence)

    ui = UI(HarnessProvider())
    ctx = create_game_context(ui, skip_character_creation=True)
    # ensure narration stays off
    ctx["flags"] = {"narration_enabled": False}

    start_game(ctx)

    # Drive flow
    game_step(ctx, {"action": "generate_encounter"})
    game_step(ctx, {"action": "enter_encounter"})
    game_step(ctx, {"action": "declare_chain", "chain": ["Basic Strike"]})
    game_step(ctx, {"action": "tick"})  # resolve chain


if __name__ == "__main__":
    if os.getenv("DEBUGPY"):
        import debugpy

        debugpy.listen(("0.0.0.0", 5678))
        print("Waiting for debugger attach on 5678...")
        debugpy.wait_for_client()
        print("Debugger attached.")
    main()
