from typing import Dict, Any
import json
from pathlib import Path


class SceneLoader:
    """
    Resolves a scene definition into concrete runtime data:
    - environment
    - monsters
    - traps
    - hazards
    - loot tables

    No game logic here. Pure data wiring.
    """

    def __init__(self, data_root: str | Path):
        self.data_root = Path(data_root)

        self._cache: Dict[str, Dict[str, Any]] = {}

    # ──────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────

    def load_scene(self, scene_def: Dict[str, Any]) -> Dict[str, Any]:
        """
        Returns a fully resolved scene bundle ready for the engine.
        """
        return {
            "id": scene_def["id"],
            "title": scene_def.get("title"),
            "environment": self._load_environment(scene_def),
            "encounter": self._load_encounter(scene_def),
            "loot": self._load_loot(scene_def),
            "flags": scene_def.get("flags", {}).copy(),
            "metrics": scene_def.get("metrics", {}).get("track", []),
            "raw": scene_def,  # keep original for reference
        }

    # ──────────────────────────────────────────────
    # Environment
    # ──────────────────────────────────────────────

    def _load_environment(self, scene_def):
        env_id = scene_def.get("environment", {}).get("id")
        if not env_id:
            return None
        return self._load_json("environments", env_id)

    # ──────────────────────────────────────────────
    # Encounter
    # ──────────────────────────────────────────────

    def _load_encounter(self, scene_def):
        enc = scene_def.get("encounter", {})

        return {
            "monsters": [
                {
                    "id": m["id"],
                    "count": m.get("count", 1),
                    "data": self._load_monster(m["id"]),
                }
                for m in enc.get("monsters", [])
            ],

            "traps": [
                {
                    "id": t["id"],
                    "count": t.get("count", 1),
                    "data": self._load_trap(t["id"]),
                }
                for t in enc.get("traps", [])
            ],

            "hazards": [
                self._load_json("hazards", hid)
                for hid in enc.get("hazards", [])
            ],
        }

    # ──────────────────────────────────────────────
    # Loot
    # ──────────────────────────────────────────────

    def _load_loot(self, scene_def):
        return [
            self._load_json("loot", loot_id)
            for loot_id in scene_def.get("loot_table", [])
        ]

    def _load_monster(self, monster_id: str) -> Dict[str, Any]:
        """
        Monsters are stored in a single bestiary.json inside the monsters folder.
        """
        key = f"monsters:{monster_id}"
        if key in self._cache:
            return self._cache[key]

        bestiary_path = self.data_root / "monsters" / "bestiary.json"
        if not bestiary_path.exists():
            raise FileNotFoundError(f"Missing bestiary file: {bestiary_path}")

        with open(bestiary_path, "r", encoding="utf-8") as f:
            bestiary = json.load(f)

        lookup = {m.get("id"): m for m in bestiary.get("enemies", [])}
        if monster_id not in lookup:
            raise KeyError(f"Monster id {monster_id} not found in bestiary")

        self._cache[key] = lookup[monster_id]
        return self._cache[key]

    def _load_trap(self, trap_id: str) -> Dict[str, Any]:
        """
        Traps are stored in a single traps.json at data_root.
        """
        key = f"traps:{trap_id}"
        if key in self._cache:
            return self._cache[key]

        traps_path = self.data_root / "traps.json"
        if not traps_path.exists():
            raise FileNotFoundError(f"Missing traps file: {traps_path}")

        with open(traps_path, "r", encoding="utf-8") as f:
            traps_data = json.load(f)

        lookup = {t.get("id"): t for t in traps_data.get("traps", [])}
        if trap_id not in lookup:
            raise KeyError(f"Trap id {trap_id} not found in traps.json")

        self._cache[key] = lookup[trap_id]
        return self._cache[key]

    # ──────────────────────────────────────────────
    # JSON loading + caching
    # ──────────────────────────────────────────────

    def _load_json(self, folder: str, item_id: str) -> Dict[str, Any]:
        """
        item_id maps directly to filename: <id>.json
        """
        key = f"{folder}:{item_id}"
        if key in self._cache:
            return self._cache[key]

        path = self.data_root / folder / f"{item_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"Missing data file: {path}")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self._cache[key] = data
        return data
