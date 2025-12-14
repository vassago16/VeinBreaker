"""
Central place to host long-lived game-wide singletons (e.g., narrator, narration manager).
"""

try:
    from openai import OpenAI  # type: ignore
    from ai.narrator import VeinbreakerNarrator, load_api_key
    from engine.narration_manager import NarrationManager

    _api_key = load_api_key()
    if _api_key:
        _client = OpenAI(api_key=_api_key)
        _narrator = VeinbreakerNarrator(_client, model="gpt-4o-mini")
        NARRATOR = _narrator
        NARRATION = NarrationManager(_narrator)
    else:
        print("[Narrator] No API key found in env or apiKey file; narration disabled.")
        NARRATOR = None
        NARRATION = None
except Exception as e:
    print(f"[Narrator] Failed to initialize narrator: {e}")
    # In test/offline contexts, narration stays disabled.
    NARRATOR = None
    NARRATION = None
