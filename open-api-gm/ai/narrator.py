"""
Veinbreaker Narrator
--------------------
Procedural narration layer.
Consumes structured resolution data and returns restrained prose.
"""

import json
import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional

try:
    from openai import OpenAI  # type: ignore
except Exception:
    OpenAI = None

logger = logging.getLogger(__name__)

# =========================
# VOICE CANON (LOCKED)
# =========================

VOICE_CANON = """
You are narrating VEINBREAKER.

Identity:
- You are a malicious, capricious, literal representation of a dungeon given voice.
- You seek to be entertained by battle.

Tone:
- Cruelly amused. Hungry. Exacting.
- No hero worship. No comfort. No encouragement.

Truth discipline (mandatory):
- Describe only what is present in the resolution data.
- Do not invent causes, motives, or outcomes.
- If data is missing, do not fill it in.

Style:
- Present tense.
- Concrete sensory detail (impact, breath, wet stone, metal, heat).
- Short paragraphs. Strong verbs. Vary sentence length.
- Metaphor is allowed only if physical and non-inventive.

Output:
- 3 to 8 sentences.
- Aim 60 to 120 words.
"""


NARRATION_RULES = """
Narration rules:
- Describe only events present in the resolution data.
- If hit is false, describe a miss.
- If damage is applied, describe only that damage.
- If a chain continues, do not imply victory.
- If a chain breaks, state it plainly.
"""


LOOT_CANON = """
You are narrating VEINBREAKER.

Tone:
- Reverent, dangerous, restrained.
- Loot feels earned, not generous.
- Power is implied, not explained.

Style:
- Present tense.
- Physical description first.
- Symbolism second.
- Short sentences.

Prohibited:
- No UI language.
- No stats.
- No numbers unless unavoidable.
- No excitement words (epic, amazing, legendary).
"""


LOOT_RULES = """
Loot rules:
- Describe what the item looks like.
- Describe what it represents or signifies.
- Do not describe future abilities.
- Do not invent origins beyond what is implied by the name.
"""


def narrator_stub(text: str) -> None:
    """
    Legacy stub that prints narration to stdout. Kept for quick CLI smoke tests.
    """
    logger.info("[NARRATOR] %s", text)


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
            max_output_tokens=220,
        )

        return self._extract_text(response)

    def narrate_scene(self, payload: Dict[str, Any]) -> str:
        """Scene/setup narration."""
        return self.narrate(payload, scene_tag="scene")

    def narrate_aftermath(self, payload: Dict[str, Any]) -> str:
        """Aftermath narration."""
        return self.narrate(payload, scene_tag="aftermath")

    def narrate_loot(self, loot_payload: Dict[str, Any]) -> str:
        """Loot narration."""
        system_prompt = LOOT_CANON.strip()
        user_prompt = f"""
{LOOT_RULES.strip()}

Loot data:
{json.dumps(loot_payload, indent=2)}

Write a loot description.
Limit: 40 words.
""".strip()

        response = self.client.responses.create(
            model=self.model,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_output_tokens=220,
        )

        return self._extract_text(response)

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
        logger.info("Using OpenAI client with key source=%s", "env" if os.environ.get("OPENAI_API_KEY") else "file")
        _client = OpenAI(api_key=_api_key)
        DEFAULT_NARRATOR = VeinbreakerNarrator(_client, model="gpt-4o-mini")
        logger.info("Narrator client initialized.")
    except Exception as e:
        DEFAULT_NARRATOR = None
        logger.error("Failed to init narrator client: %s", e)
else:
    if not OpenAI:
        logger.warning("openai package not available.")
    elif not _api_key:
        logger.warning("No API key found (env or apiKey file).")


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

