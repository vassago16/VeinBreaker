"""
Veinbreaker Narrator
--------------------
Procedural narration layer.
Consumes structured resolution data and returns restrained prose.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional

try:
    from openai import OpenAI  # type: ignore
except Exception:
    OpenAI = None


# =========================
# VOICE CANON (LOCKED)
# =========================

VOICE_CANON = """
You are narrating VEINBREAKER.

Tone:
- Brutal, restrained, procedural.
- No heroic language.
- No emotional interpretation.
- Violence is described clinically.

Style:
- Present tense.
- Short sentences.
- Physical cause → physical effect.
- No metaphors unless strictly physical.

Prohibited:
- No inner thoughts.
- No encouragement or advice.
- No explanation of rules.
- No invented details.
- No future resolution.

Output:
- 2 to 5 sentences.
- Hard limit: 40 words.
"""


NARRATION_RULES = """
Narration rules:
- Describe only events present in the resolution data.
- If hit is false, describe a miss.
- If damage is applied, describe only that damage.
- If a chain continues, do not imply victory.
- If a chain breaks, state it plainly.
"""


def narrator_stub(text: str) -> None:
    """
    Legacy stub that prints narration to stdout. Kept for quick CLI smoke tests.
    """
    print("\n[NARRATOR]\n" + text + "\n")


def load_api_key() -> Optional[str]:
    # Environment first
    key = os.environ.get("OPENAI_API_KEY")
    if key:
        return key
    # fallback to open-api-gm/apiKey file
    key_path = Path(__file__).resolve().parent.parent / "apiKey"
    if key_path.exists():
        val = key_path.read_text(encoding="utf-8").strip()
        if val:
            return val
    return None


# =========================
# NARRATOR
# =========================

class VeinbreakerNarrator:
    def __init__(self, openai_client, model: str):
        """
        openai_client: already-authenticated OpenAI client
        model: e.g. "gpt-4o-mini" or "gpt-5-nano"
        """
        self.client = openai_client
        self.model = model

    def narrate(
        self,
        resolution: Dict[str, Any],
        *,
        scene_tag: Optional[str] = None
    ) -> str:
        """
        resolution: structured, machine-truth combat or action result
        scene_tag: optional ("combat", "interrupt", "kill", "miss", etc.)
        """

        # Defensive copy
        payload = json.dumps(resolution, indent=2)

        system_prompt = VOICE_CANON.strip()
        user_prompt = f"""
{NARRATION_RULES.strip()}

Scene: {scene_tag or "unspecified"}

Resolution data:
{payload}

Narrate the resolution.
""".strip()

        response = self.client.responses.create(
            model=self.model,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_output_tokens=120,  # clamps verbosity
        )

        return self._extract_text(response)

    def narrate_scene(self, payload: Dict[str, Any]) -> str:
        """Scene/setup narration."""
        return self.narrate(payload, scene_tag="scene")

    def narrate_aftermath(self, payload: Dict[str, Any]) -> str:
        """Aftermath narration."""
        return self.narrate(payload, scene_tag="aftermath")

    # =========================
    # INTERNALS
    # =========================

    def _extract_text(self, response) -> str:
        """
        Safely extract text from OpenAI Responses API output.
        """
        parts = []
        for item in response.output:
            # message content
            if getattr(item, "type", None) == "message":
                for c in item.content:
                    if getattr(c, "type", None) == "output_text":
                        parts.append(c.text)

        text = " ".join(parts).strip()
        return self._postprocess(text)

    def _postprocess(self, text: str) -> str:
        """
        Final clamps to enforce tone discipline.
        """
        # Remove accidental second-person encouragement
        forbidden_phrases = [
            "you feel",
            "you sense",
            "you realize",
            "it seems",
            "perhaps",
            "might",
        ]

        lowered = text.lower()
        for phrase in forbidden_phrases:
            if phrase in lowered:
                # hard truncate on violation
                return text.split(".")[0].strip() + "."

        return text


# Default narrator instance for simple imports (e.g., play.py) when OpenAI is available.
_api_key = load_api_key()
DEFAULT_NARRATOR = None
if OpenAI and _api_key:
    try:
        print(f"[Narrator] Using OpenAI client with key source={'env' if os.environ.get('OPENAI_API_KEY') else 'file'}")
        _client = OpenAI(api_key=_api_key)
        DEFAULT_NARRATOR = VeinbreakerNarrator(_client, model="gpt-4o-mini")
        print("[Narrator] Client initialized.")
    except Exception as e:
        print(f"[Narrator] Failed to init client: {e}")
        DEFAULT_NARRATOR = None
else:
    if not OpenAI:
        print("[Narrator] openai package not available.")
    elif not _api_key:
        print("[Narrator] No API key found (env or apiKey file).")


def narrate(resolution: Dict[str, Any], scene_tag: Optional[str] = None, *_, **__) -> str:
    """
    Convenience facade: use the default narrator if configured, else return empty string.
    """
    if DEFAULT_NARRATOR:
        try:
            return DEFAULT_NARRATOR.narrate(resolution, scene_tag=scene_tag)
        except Exception:
            return ""
    return "no narrator"
