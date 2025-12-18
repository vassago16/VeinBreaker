"""
Minimal harness to step through a basic encounter and resolve a one-link chain
using a deterministic roll sequence. Designed to run locally without the web UI.

Usage:
  python tools/test_basic_chain.py
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, List

# Ensure project root on path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from play import create_game_context, start_game, game_step  # noqa: E402
from ui.ui import UI  # noqa: E402
from ui.provider import UIProvider  # noqa: E402


# ---- Deterministic roll injection ------------------------------------------------
def make_rolls(sequence: List[int]):
    """Return a roll function that pops from a predefined sequence."""
    rolls = list(sequence)

    def _roll(_dice: str) -> int:
        if not rolls:
            raise RuntimeError("Out of predefined rolls.")
        return rolls.pop(0)

    return _roll


# ---- Dummy UI provider (blocking) -------------------------------------------------
class HarnessProvider(UIProvider):
    is_blocking = True

    def __init__(self):
        self.events: List[Any] = []

    def scene(self, text: str, data: Any = None):
        self.events.append(("scene", text))
        print(f"[SCENE] {text[:80]}...")

    def narration(self, text: str, data: Any = None):
        self.events.append(("narration", text))
        print(f"[NARRATION] {text}")

    def system(self, text: str, data: Any = None):
        self.events.append(("system", text))
        print(f"[SYSTEM] {text}")

    def error(self, text: str, data: Any = None):
        self.events.append(("error", text))
        print(f"[ERROR] {text}")

    def choice(self, prompt: str, options: list[str]):
        self.events.append(("choice", prompt, options))
        # Always take the first option for this harness
        print(f"[CHOICE] {prompt} -> picking index 0 ({options[0]})")
        return 0

    def clear(self, target: str = "narration"):
        self.events.append(("clear", target))


def main():
    # Deterministic rolls for attacker/defender alternating.
    roll_sequence = [
        16, 15,  # chain attack / defender
        9, 18,
        17, 12,
        4, 8,
        3, 14,
        1, 6,
    ]

    # Monkeypatch roll used by the chain resolver
    import engine.action_resolution as ar  # type: ignore

    ar.roll = make_rolls(roll_sequence)

    ui = UI(HarnessProvider())
    ctx = create_game_context(ui, skip_character_creation=True)
    start_game(ctx)

    # Drive actions manually
    game_step(ctx, {"action": "generate_encounter"})
    game_step(ctx, {"action": "enter_encounter"})
    game_step(ctx, {"action": "declare_chain", "chain": ["Basic Strike"]})
    game_step(ctx, {"action": "tick"})  # resolve the chain


if __name__ == "__main__":
    main()
