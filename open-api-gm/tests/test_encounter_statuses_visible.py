import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.combat_state import register_participant, status_add  # noqa: E402
from play import emit_authoritative_player_update  # noqa: E402


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
        return None

    def choice(self, prompt, options):
        return 0


class TestEncounterStatusesVisible(unittest.TestCase):
    def test_player_character_update_includes_encounter_stagger(self):
        state = {"encounter": {"participants": {}}, "party": {"members": []}}
        player = {"name": "P", "resources": {"hp": 10, "hp_max": 10, "resolve": 1, "resolve_cap": 5}}
        register_participant(state, key="player", entity=player, side="player")
        status_add(state, player, status="Stagger", stacks=1, duration_rounds=1)

        session = _Session()
        ui = _UI(session)
        emit_authoritative_player_update(ui, state, player)

        ev = next((e for e in session.events if isinstance(e, dict) and e.get("type") == "character_update"), None)
        self.assertIsNotNone(ev)
        st = (ev.get("character") or {}).get("statuses") or {}
        self.assertIn("stagger", st)
        self.assertEqual(st["stagger"].get("stacks"), 1)


if __name__ == "__main__":
    unittest.main()

