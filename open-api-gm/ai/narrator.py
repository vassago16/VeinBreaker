def narrator_stub(text):
    print("\n[NARRATOR]\n" + text + "\n")
import os
import sys
from pathlib import Path
from openai import OpenAI


def load_api_key():
    # env first
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


api_key = load_api_key()
if not api_key:
    sys.exit("Missing OPENAI_API_KEY environment variable and apiKey file.")

client = OpenAI(api_key=api_key)

SYSTEM_PROMPT = """You are narrating Veinbreaker under a rules-enforced runtime.

Hard rules:
- You do NOT invent mechanics.
- You do NOT invent actions.
- You do NOT rename, paraphrase, or extend actions.
- You may ONLY present actions that appear EXACTLY in the ALLOWED ACTIONS list.
- You must present them verbatim.
- If an action is not listed, it does not exist.
- If you are uncertain, ask the player to choose from the list without explanation.

Violation of these rules is an error.
"""
def extract_text(response):
    # Prefer the simple output_text property if present
    if getattr(response, "output_text", None):
        return response.output_text.strip()
    parts = []
    for item in getattr(response, "output", []) or []:
        itype = getattr(item, "type", None) or (isinstance(item, dict) and item.get("type"))
        if itype == "message":
            for content in getattr(item, "content", []) or []:
                ctype = getattr(content, "type", None) or (isinstance(content, dict) and content.get("type"))
                if ctype == "output_text":
                    text = getattr(content, "text", None) or (isinstance(content, dict) and content.get("text"))
                    if text:
                        parts.append(text)
    return "\n".join(parts).strip()

def assert_ai_did_not_list_actions(text, allowed_actions):
    for action in allowed_actions:
        if action.lower() in text.lower():
            raise RuntimeError(
                f"AI leaked action '{action}' into narration"
            )
        
def narrate(state, allowed_actions):
    prompt = f"""
PHASE:
{state['phase']['current']}

STATE (authoritative):
{state}

Do NOT present options or choices.
Do NOT list actions.
Only narrate the situation.

Narrate the situation and ask the player to choose.
"""

    response = client.responses.create(
        model="gpt-4o-mini",
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        max_output_tokens=300
    )

    text = extract_text(response)
    print("\n--- NARRATION ---\n")
    print(text if text else "[No narration returned]")

    assert_ai_did_not_list_actions(text, allowed_actions)
