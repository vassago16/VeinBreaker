import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import play  # noqa: E402


class _Session:
    def __init__(self):
        self.events = []

    def emit(self, payload):
        self.events.append(payload)


class _Provider:
    def __init__(self, session):
        self.session = session


class _UI:
    is_blocking = False

    def __init__(self, session):
        self.provider = _Provider(session)

    def system(self, text):
        # web UI ignores this; events drive rendering
        return None

    def choice(self, prompt, options):
        return 0


class TestEnemyInterruptTelegraphOrder(unittest.TestCase):
    def test_enemy_declare_log_before_interrupt_window(self):
        session = _Session()
        ui = _UI(session)
        state = {
            "phase": {"current": "chain_resolution"},
            "party": {"members": [{"resources": {"resolve": 3}, "abilities": []}]},
            "enemies": [{"name": "Goblin", "moves": [{"name": "Stab", "type": "attack"}]}],
        }
        ctx = {"state": state, "ui": ui}

        play.handle_enemy_turn(ctx, {})

        types = [e.get("type") for e in session.events if isinstance(e, dict)]
        self.assertIn("interrupt_window", types)
        # Ensure the telegraph combat log event is emitted before the window.
        idx_window = types.index("interrupt_window")
        # emit_combat_log uses type="combat_log"
        idx_log = types.index("combat_log")
        self.assertLess(idx_log, idx_window)


if __name__ == "__main__":
    unittest.main()

