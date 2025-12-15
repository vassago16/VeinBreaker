from __future__ import annotations

from typing import Any, Dict, List, Optional
from ui.provider import UIProvider


class UI:
    """
    The game talks to UI, not to a specific provider.
    """

    def __init__(self, provider: UIProvider):
        self.provider = provider

    def scene(self, text: str, data: Optional[Dict[str, Any]] = None) -> None:
        self.provider.scene(text, data)

    def narration(self, text: str, data: Optional[Dict[str, Any]] = None) -> None:
        self.provider.narration(text, data)

    def loot(self, text: str, data: Optional[Dict[str, Any]] = None) -> None:
        self.provider.loot(text, data)

    def system(self, text: str, data: Optional[Dict[str, Any]] = None) -> None:
        self.provider.system(text, data)

    def error(self, text: str, data: Optional[Dict[str, Any]] = None) -> None:
        self.provider.error(text, data)

    def choice(self, prompt: str, options: List[str], data: Optional[Dict[str, Any]] = None) -> int:
        return self.provider.choice(prompt, options, data)

    def text_input(self, prompt: str, data: Optional[Dict[str, Any]] = None) -> str:
        return self.provider.text_input(prompt, data)
