import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class TestServerStepRequestIncludesStat(unittest.TestCase):
    def test_step_request_keeps_stat_field(self):
        import server  # noqa: E402

        req = server.StepRequest(session_id="s", action="safe_room_stat_up", stat="AGI")
        self.assertEqual(req.stat, "AGI")


if __name__ == "__main__":
    unittest.main()

